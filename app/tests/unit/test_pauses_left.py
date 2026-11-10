"""`pausesLeft` del tick: pausas que todavía no empezaron (sin contar la en curso).

Se prueba en tres capas, siempre contra el mismo contrato:
- la simulación (`MatchSession` / `TickResult.pauses_left`), que es la única fuente,
- el payload y el loop en tiempo real (`MatchRunner`), con conexión tardía y reconexión,
- la consistencia con el 409 `noPausesLeft` de las sustituciones (GET y PUT).
"""

import asyncio
from itertools import groupby
from unittest.mock import create_autospec

import pytest

from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.substitution_abstract import AbstractSubstitutionRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.services.match_broadcast import TickContext, _closing, build_tick_payload
from app.services.match_runner import MatchRunner
from app.services.substitution_service import SubstitutionService
from app.simulation import constants as C
from app.simulation import match_rules
from app.simulation.match_rules import Event, MatchSession, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.run import default_team as make_team
from app.tests.unit import penalty_helpers as ph
from app.tests.unit.match_ws_fakes import FakeMatchRepo
from app.tests.unit.test_match_runner import FakeManager, FakeWs, build
from app.tests.unit.tick_schema import TickPayload

CTX = TickContext(club_1="Club Uno", club_2="Club Dos", countdown_seconds=1)

# 4 períodos, 2 s de juego, cuentas y pausas de 1 s (20 ticks): 220 ticks en total.
SMALL = dict(periods=4, pause_seconds=1, duration=2)
SMALL_TOTAL = 20 + 40 + 3 * (20 + 20)


# --- helpers -------------------------------------------------------------------


def idle_session(
    duration, *, countdown=C.COUNTDOWN_SECONDS, pause=C.PAUSE_SECONDS, periods=4, allow_draws=True
) -> MatchSession:
    """Partido sin juego (nadie toca la pelota: 0 a 0), con el calendario de pausas real."""
    home, away = ph.team(ph.IDLE, 0), ph.team(ph.IDLE, 10)
    state = create_initial_state(home.players, away.players, 1)
    return MatchSession(
        state,
        match_rules.behaviors_by_key(home, away),
        duration,
        countdown_seconds=countdown,
        periods=periods,
        pause_seconds=pause,
        allow_draws=allow_draws,
    )


def drain(session: MatchSession) -> list[TickResult]:
    ticks = []
    while not session.finished:
        ticks.append(session.advance())
    return ticks


def runs(ticks):
    """[(fase, pausesLeft)] sin repeticiones consecutivas."""
    return [key for key, _ in groupby((tick.phase, tick.pauses_left) for tick in ticks)]


def pause_events(ticks):
    return [index for index, tick in enumerate(ticks) if tick.event is Event.PAUSE]


# --- la simulación: secuencia de valores y tick exacto del cambio --------------


def test_full_match_sequence_of_values_by_phase():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    assert runs(ticks) == [
        (Phase.COUNTDOWN, 3),  # período 1
        (Phase.PLAYING, 3),
        (Phase.PAUSED, 2),  # tras la 1.ª pausa
        (Phase.COUNTDOWN, 2),
        (Phase.PLAYING, 2),
        (Phase.PAUSED, 1),  # tras la 2.ª
        (Phase.COUNTDOWN, 1),
        (Phase.PLAYING, 1),
        (Phase.PAUSED, 0),  # tras la 3.ª: período 4
        (Phase.COUNTDOWN, 0),
        (Phase.PLAYING, 0),
        (Phase.FINISHED, 0),
    ]


def test_value_is_3_from_the_very_first_tick_countdown_included():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    assert (ticks[0].phase, ticks[0].event, ticks[0].pauses_left) == (
        Phase.COUNTDOWN,
        Event.PERIOD_START,
        3,
    )


def test_the_tick_with_the_pause_event_already_carries_the_decremented_value():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    starts = pause_events(ticks)
    assert len(starts) == 3
    for number, index in enumerate(starts, start=1):
        assert ticks[index].phase is Phase.PAUSED
        assert ticks[index].pauses_left == 3 - number  # 2, 1, 0 en el mismo tick del evento
        assert ticks[index - 1].pauses_left == 3 - number + 1  # el anterior todavía trae el viejo
        assert ticks[index - 1].phase is Phase.PLAYING


@pytest.mark.parametrize(
    ("duration", "starts"),
    [
        (C.FRIENDLY_MATCH_DURATION * 60, [45.0, 90.0, 135.0]),  # amistoso: 0:45, 1:30 y 2:15
        (60, [15.0, 30.0, 45.0]),  # liga de 1 minuto: 1/4, 1/2 y 3/4
        (240, [60.0, 120.0, 180.0]),  # liga de 4 minutos
        (100, [25.0, 50.0, 75.0]),
    ],
)
def test_the_value_follows_the_real_pause_schedule_in_friendlies_and_leagues(duration, starts):
    session = idle_session(duration)
    assert session.pause_starts == starts
    ticks = drain(session)
    begins = [ticks[index] for index in pause_events(ticks)]
    assert [tick.elapsed for tick in begins] == starts  # las pausas empiezan en el calendario
    assert [tick.pauses_left for tick in begins] == [2, 1, 0]
    assert ticks[0].pauses_left == 3 and ticks[-1].pauses_left == 0
    # Cada tick de juego trae las pausas que todavía no llegaron a su minuto de juego:
    # el último tick antes de una pausa (elapsed == corte) todavía no la cuenta como empezada.
    for tick in (tick for tick in ticks if tick.phase is Phase.PLAYING):
        assert tick.pauses_left == sum(start >= tick.elapsed for start in starts)


def test_a_pause_does_not_count_itself_through_its_whole_duration():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    for first in pause_events(ticks):
        pause = ticks[first : first + 20]
        assert {tick.phase for tick in pause} == {Phase.PAUSED}
        assert len({tick.pauses_left for tick in pause}) == 1


def test_the_value_is_the_calendar_not_a_fixed_number():
    # Sin pausas programadas (un período): no hay nada por empezar.
    assert {tick.pauses_left for tick in drain(idle_session(2, countdown=1, periods=1))} == {0}
    # Pausas de 0 s: el calendario no tiene ninguna.
    assert {tick.pauses_left for tick in drain(idle_session(8, countdown=1, pause=0))} == {0}
    # Dos períodos: una sola pausa.
    ticks = drain(idle_session(8, countdown=1, pause=1, periods=2))
    assert runs(ticks)[0] == (Phase.COUNTDOWN, 1)
    assert [ticks[index].pauses_left for index in pause_events(ticks)] == [0]


# --- penales ---------------------------------------------------------------------


def test_the_shootout_and_finished_keep_the_value_at_0():
    ticks = drain(idle_session(8, countdown=1, pause=1, allow_draws=False))  # 0 a 0: tanda
    assert any(tick.event is Event.PENALTIES_START for tick in ticks)
    # el período 4 también estaba en 0 antes de la tanda
    assert runs(ticks)[-3:] == [(Phase.PLAYING, 0), (Phase.PENALTIES, 0), (Phase.FINISHED, 0)]


def test_a_match_that_ends_in_a_draw_without_a_shootout_also_ends_with_0():
    ticks = drain(idle_session(8, countdown=1, pause=1, allow_draws=True))
    assert not any(tick.phase is Phase.PENALTIES for tick in ticks)
    assert (ticks[-1].phase, ticks[-1].pauses_left) == (Phase.FINISHED, 0)


# --- el payload -------------------------------------------------------------------


def _result(phase, pauses_left) -> TickResult:
    state = create_initial_state(make_team().players, make_team(first_id=10).players, 1)
    return TickResult(3, phase, None, state, 0, 0, 5.0, 5.0, 1, pauses_left=pauses_left)


@pytest.mark.parametrize("pauses_left", [0, 1, 2, 3])
def test_payload_carries_pauses_left_as_an_integer(pauses_left):
    payload = build_tick_payload(_result(Phase.PLAYING, pauses_left), CTX)
    assert payload["pausesLeft"] == pauses_left and type(payload["pausesLeft"]) is int
    TickPayload.model_validate(payload)


def test_every_tick_of_a_full_match_validates_against_the_contract():
    for tick in drain(idle_session(8, countdown=1, pause=1, allow_draws=False)):
        payload = build_tick_payload(tick, CTX)
        TickPayload.model_validate(payload)  # `pausesLeft` obligatorio, entero de 0 a 3
        assert payload["pausesLeft"] == tick.pauses_left


# --- el loop en tiempo real -------------------------------------------------------


def run(runner):
    async def main():
        await runner.start(1)
        await asyncio.gather(*list(_closing))

    asyncio.run(main())


def stream(**over):
    """El stream completo de ticks de un partido chico, como lo recibe un suscriptor."""
    websocket = FakeWs()
    run(build(FakeManager([websocket]), FakeMatchRepo(), **{**SMALL, **over}))
    return websocket.received


def phase_values(ticks):
    return [key for key, _ in groupby((tick["phase"], tick["pausesLeft"]) for tick in ticks)]


def test_runner_stream_has_the_full_sequence_and_validates():
    ticks = stream()
    assert len(ticks) == SMALL_TOTAL
    for tick in ticks:
        TickPayload.model_validate(tick)
    assert phase_values(ticks) == [
        ("countdown", 3),
        ("playing", 3),
        ("paused", 2),
        ("countdown", 2),
        ("playing", 2),
        ("paused", 1),
        ("countdown", 1),
        ("playing", 1),
        ("paused", 0),
        ("countdown", 0),
        ("playing", 0),
        ("finished", 0),
    ]


def test_runner_decrements_on_the_exact_tick_of_the_pause_event():
    ticks = stream()
    starts = [
        index
        for index, tick in enumerate(ticks)
        if tick["event"] and tick["event"]["type"] == "pause"
    ]
    assert len(starts) == 3
    for number, index in enumerate(starts, start=1):
        assert ticks[index]["pausesLeft"] == 3 - number
        assert ticks[index - 1]["pausesLeft"] == 3 - number + 1


def test_runner_with_pauses_of_another_length_keeps_the_same_values():
    assert phase_values(stream(pause_seconds=2)) == phase_values(stream())


def test_a_shootout_through_the_runner_stays_at_0(monkeypatch):
    monkeypatch.setattr(MatchSession, "_goes_to_penalties", lambda self: True)
    ticks = stream(allow_draws=False)
    for tick in ticks:
        TickPayload.model_validate(tick)
    assert phase_values(ticks)[-3:] == [("playing", 0), ("penalties", 0), ("finished", 0)]


def late_joiners(join_at, *, reconnect=False, **over):
    """Un suscriptor entra con el partido en marcha (sin replay) en cada tick de `join_at`.

    Con `reconnect`, el que estaba conectado se cae justo antes y el nuevo lo reemplaza.
    Devuelve {tick en que entró: primer tick que recibió}.
    """
    first = FakeWs()
    manager = FakeManager([first])
    late: dict[int, FakeWs] = {}
    state = {"current": first, "sent": 0}

    def probe(_tick):
        state["sent"] += 1  # ticks transmitidos hasta ahora (lo cuenta quien está conectado)
        sent = state["sent"]
        if sent in join_at and sent not in late:
            joiner = FakeWs()
            late[sent] = joiner
            if reconnect:
                state["current"].closed = (1006, "lost")
                state["current"].probe = None
                joiner.probe = probe
            manager.sockets.append(joiner)
            state["current"] = joiner

    first.probe = probe
    run(build(manager, FakeMatchRepo(), **{**SMALL, **over}))
    return {sent: joiner.received[0] for sent, joiner in late.items() if joiner.received}


def test_a_late_client_gets_the_right_value_in_its_first_tick_at_every_point_of_the_match():
    reference = stream()
    joined = late_joiners(set(range(1, SMALL_TOTAL)))
    assert set(joined) == set(range(1, SMALL_TOTAL))
    for sent, first_tick in joined.items():
        assert first_tick["pausesLeft"] == reference[sent]["pausesLeft"], sent
        assert first_tick["phase"] == reference[sent]["phase"]
        TickPayload.model_validate(first_tick)


def test_a_client_that_reconnects_knows_the_value_from_its_first_tick():
    reference = stream()
    points = set(range(1, SMALL_TOTAL, 3))
    joined = late_joiners(points, reconnect=True)
    assert set(joined) == points
    for sent, first_tick in joined.items():
        assert first_tick["pausesLeft"] == reference[sent]["pausesLeft"], sent


def test_players_and_spectators_receive_the_same_value_tick_by_tick():
    player, spectator = FakeWs(), FakeWs()

    class TwoUsers(FakeManager):
        def subscribers(self, match_id):
            users = zip(self.sockets, (7, 99))
            return [
                (websocket, user_id) for websocket, user_id in users if websocket.closed is None
            ]

    run(build(TwoUsers([player, spectator]), FakeMatchRepo(), **SMALL))
    assert player.received == spectator.received  # la transmisión es idéntica
    assert {tick["pausesLeft"] for tick in player.received} == {0, 1, 2, 3}


def test_the_runner_progress_carries_the_same_value_as_the_tick():
    seen = []
    websocket = FakeWs()
    runner = build(FakeManager([websocket]), FakeMatchRepo(), **SMALL)
    websocket.probe = lambda tick: seen.append((tick["pausesLeft"], runner.progress(1).pauses_left))
    run(runner)
    assert len(seen) == SMALL_TOTAL
    assert all(from_tick == from_progress for from_tick, from_progress in seen)


# --- consistencia con el 409 de las sustituciones ---------------------------------


class Scenario:
    """Un SubstitutionService real mirando el progreso del runner mientras se juega."""

    def __init__(self, repo: FakeMatchRepo, runner: MatchRunner):
        matches = create_autospec(AbstractMatchRepository, instance=True)
        matches.get_players.side_effect = lambda _id: MatchPlayersData(
            id=1,
            league_id=None,
            status=MatchStatus(repo.states[1].status),
            user_1_id=7,
            user_2_id=8,
        )
        teams = create_autospec(AbstractTeamRepository, instance=True)
        teams.get_member_id.return_value = 100  # titular y suplente válidos
        substitutions = create_autospec(AbstractSubstitutionRepository, instance=True)
        substitutions.list_by_match.return_value = []
        substitutions.list_applied_by_match.return_value = []
        self.service = SubstitutionService(matches, substitutions, runner, teams)

    def put(self):
        try:
            self.service.request_substitution(7, 1, {"starterId": 10, "substituteId": 13})
            return 204
        except ApiError as error:
            return (error.status_code, error.code)

    def get(self):
        try:
            self.service.get_substitutions(7, 1)
            return 200
        except ApiError as error:
            return (error.status_code, error.code)


def expected_responses(tick, status):
    """Qué deben responder PUT y GET para este tick, según el contrato."""
    if status != "started":
        return (409, "matchNotStarted"), (409, "matchNotStarted")
    if tick["phase"] == "penalties":
        return (409, "matchInPenalties"), (409, "matchInPenalties")
    left = tick["pausesLeft"]
    put = 204 if left > 0 else (409, "noPausesLeft")
    # el GET dentro de la última pausa muestra lo aplicado (200); fuera de ella, 409 con 0
    get = 200 if left > 0 or tick["phase"] == "paused" else (409, "noPausesLeft")
    return put, get


def audit(**over):
    """Juega el partido y, en cada tick, compara el REST con lo que dice el tick."""
    repo = FakeMatchRepo()
    repo.add(1)
    websocket = FakeWs()
    runner = build(FakeManager([websocket]), repo, **{**SMALL, **over})
    scenario = Scenario(repo, runner)
    audited = []

    def probe(tick):
        if tick["phase"] == "finished":  # el partido ya se guardó como terminado
            return
        status = repo.states[1].status
        audited.append(
            (tick, status, scenario.put(), scenario.get(), expected_responses(tick, status))
        )

    websocket.probe = probe
    run(runner)
    return audited


def test_rest_409_matches_pauses_left_on_every_tick_of_the_match():
    audited = audit()
    assert len(audited) == SMALL_TOTAL - 1
    for tick, status, put, get, (want_put, want_get) in audited:
        where = (tick["phase"], tick["pausesLeft"], status)
        assert put == want_put, where
        assert get == want_get, where


def test_requests_in_the_first_countdown_are_match_not_started_even_with_3_left():
    first_countdown = [
        (tick, put, get)
        for tick, status, put, get, _ in audit()
        if tick["phase"] == "countdown" and status != "started"
    ]
    assert first_countdown
    for tick, put, get in first_countdown:
        assert tick["pausesLeft"] == 3
        assert put == get == (409, "matchNotStarted")


def test_rest_during_the_shootout_is_in_penalties_and_not_no_pauses_left(monkeypatch):
    monkeypatch.setattr(MatchSession, "_goes_to_penalties", lambda self: True)
    audited = audit(allow_draws=False)
    penalties = [entry for entry in audited if entry[0]["phase"] == "penalties"]
    assert penalties
    for tick, _status, put, get, _ in penalties:
        assert tick["pausesLeft"] == 0
        assert put == get == (409, "matchInPenalties")
    # el último tick de juego (período 4) sigue siendo noPausesLeft
    last_play = [entry for entry in audited if entry[0]["phase"] == "playing"][-1]
    assert last_play[2] == (409, "noPausesLeft")


def test_a_league_style_schedule_keeps_rest_and_ticks_consistent():
    for tick, status, put, get, (want_put, want_get) in audit(pause_seconds=2, duration=4):
        assert (put, get) == (want_put, want_get), (tick["phase"], tick["pausesLeft"], status)


def test_a_match_that_is_not_played_in_this_process_has_no_pause_to_apply():
    repo = FakeMatchRepo()
    repo.add(1, MatchStatus.started)
    runner = build(FakeManager([]), repo, **SMALL)  # nunca se arrancó
    assert Scenario(repo, runner).put() == (409, "noPausesLeft")
