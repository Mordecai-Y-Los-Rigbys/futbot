"""`pausesLeft` del tick: pausas que todavía no empezaron (sin contar la en curso).

Se prueba en tres capas, siempre contra el mismo contrato:
- la simulación (`MatchSession` / `TickResult.pauses_left`), que es la única fuente,
- el payload y el loop en tiempo real (`MatchRunner`), con conexión tardía y reconexión,
- la consistencia con el 409 `noPausesLeft` de las sustituciones (GET y PUT).
"""

import asyncio
import itertools
from contextlib import contextmanager
from itertools import groupby
from unittest.mock import create_autospec

import pytest

from app.errors import ApiError
from app.models.match import MatchStatus
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.substitution_abstract import AbstractSubstitutionRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.services.match_broadcast import TickContext, build_tick_payload, _closing
from app.services.match_progress import MatchProgress
from app.services.match_runner import MatchRunner
from app.services.match_setup_service import MatchSetup
from app.services.substitution_service import SubstitutionService
from app.simulation import constants as C
from app.simulation import match_rules
from app.simulation.match_rules import Event, MatchSession, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.run import default_team as make_team
from app.tests.unit import penalty_helpers as ph
from app.tests.unit.match_ws_fakes import FakeMatchRepo, FakeSubstitutionRepo
from app.tests.unit.test_match_runner import FakeManager, FakeWs, build
from app.tests.unit.tick_schema import TickPayload

CTX = TickContext(club_1="Club Uno", club_2="Club Dos", countdown_seconds=1)

# 4 períodos, 2 s de juego, cuentas y pausas de 1 s (20 ticks): 220 ticks en total.
SMALL = dict(periods=4, pause_seconds=1, duration=2)
SMALL_TOTAL = 20 + 40 + 3 * (20 + 20)


# --- helpers -------------------------------------------------------------------


def idle_session(duration, *, countdown=C.COUNTDOWN_SECONDS, pause=C.PAUSE_SECONDS, periods=4,
                 allow_draws=True) -> MatchSession:
    """Partido sin juego (nadie toca la pelota: 0 a 0), con el calendario de pausas real."""
    t1, t2 = ph.team(ph.IDLE, 0), ph.team(ph.IDLE, 10)
    state = create_initial_state(t1.players, t2.players, 1)
    return MatchSession(
        state,
        match_rules.behaviors_by_key(t1, t2),
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
    return [k for k, _ in groupby((t.phase, t.pauses_left) for t in ticks)]


def pause_events(ticks):
    return [i for i, t in enumerate(ticks) if t.event is Event.PAUSE]


# --- la simulación: secuencia de valores y tick exacto del cambio --------------


def test_full_match_sequence_of_values_by_phase():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    assert runs(ticks) == [
        (Phase.COUNTDOWN, 3), (Phase.PLAYING, 3),  # período 1
        (Phase.PAUSED, 2), (Phase.COUNTDOWN, 2), (Phase.PLAYING, 2),  # tras la 1.ª pausa
        (Phase.PAUSED, 1), (Phase.COUNTDOWN, 1), (Phase.PLAYING, 1),  # tras la 2.ª
        (Phase.PAUSED, 0), (Phase.COUNTDOWN, 0), (Phase.PLAYING, 0),  # tras la 3.ª: período 4
        (Phase.FINISHED, 0),
    ]


def test_value_is_3_from_the_very_first_tick_countdown_included():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    assert (ticks[0].phase, ticks[0].event, ticks[0].pauses_left) == (
        Phase.COUNTDOWN, Event.PERIOD_START, 3,
    )


def test_the_tick_with_the_pause_event_already_carries_the_decremented_value():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    starts = pause_events(ticks)
    assert len(starts) == 3
    for n, i in enumerate(starts, start=1):
        assert ticks[i].phase is Phase.PAUSED
        assert ticks[i].pauses_left == 3 - n  # 2, 1, 0 en el mismo tick del evento
        assert ticks[i - 1].pauses_left == 3 - n + 1  # el tick anterior todavía trae el viejo
        assert ticks[i - 1].phase is Phase.PLAYING


def test_the_value_does_not_change_outside_the_pause_start_ticks():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    changes = [i for i in range(1, len(ticks)) if ticks[i].pauses_left != ticks[i - 1].pauses_left]
    assert changes == pause_events(ticks)


def test_only_ever_decreases_and_stays_in_0_to_3():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    values = [t.pauses_left for t in ticks]
    assert all(0 <= v <= 3 for v in values)
    assert values == sorted(values, reverse=True)


def test_value_depends_only_on_the_tick_not_on_who_saw_the_events():
    """Un cliente tardío no vio ningún `pause`: el valor sale del estado de la simulación."""
    ticks = drain(idle_session(8, countdown=1, pause=1))
    seen = 0
    for t in ticks:
        seen += t.event is Event.PAUSE
        assert t.pauses_left == 3 - seen


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
    begins = [ticks[i] for i in pause_events(ticks)]
    assert [t.elapsed for t in begins] == starts  # las pausas empiezan en el calendario real
    assert [t.pauses_left for t in begins] == [2, 1, 0]
    assert ticks[0].pauses_left == 3 and ticks[-1].pauses_left == 0
    # Cada tick de juego trae las pausas que todavía no llegaron a su minuto de juego:
    # el último tick antes de una pausa (elapsed == corte) todavía no la cuenta como empezada.
    for t in (t for t in ticks if t.phase is Phase.PLAYING):
        assert t.pauses_left == sum(s >= t.elapsed for s in starts)


def test_a_pause_does_not_count_itself_through_its_whole_duration():
    ticks = drain(idle_session(8, countdown=1, pause=1))
    for first in pause_events(ticks):
        pause = [t for t in ticks[first:first + 20]]
        assert {t.phase for t in pause} == {Phase.PAUSED}
        assert len({t.pauses_left for t in pause}) == 1


def test_the_value_is_the_calendar_not_a_fixed_number():
    # Sin pausas programadas (un período): no hay nada por empezar.
    assert {t.pauses_left for t in drain(idle_session(2, countdown=1, periods=1))} == {0}
    # Pausas de 0 s: el calendario no tiene ninguna.
    assert {t.pauses_left for t in drain(idle_session(8, countdown=1, pause=0))} == {0}
    # Dos períodos: una sola pausa.
    ticks = drain(idle_session(8, countdown=1, pause=1, periods=2))
    assert runs(ticks)[0] == (Phase.COUNTDOWN, 1)
    assert [ticks[i].pauses_left for i in pause_events(ticks)] == [0]


# --- penales ---------------------------------------------------------------------


def test_the_shootout_and_finished_keep_the_value_at_0():
    ticks = drain(idle_session(8, countdown=1, pause=1, allow_draws=False))  # 0 a 0: tanda
    assert any(t.phase is Phase.PENALTIES for t in ticks)
    assert any(t.event is Event.PENALTIES_START for t in ticks)
    assert all(t.pauses_left == 0 for t in ticks if t.phase in (Phase.PENALTIES, Phase.FINISHED))
    # el período 4 también estaba en 0 antes de la tanda
    last_play = [t for t in ticks if t.phase is Phase.PLAYING][-1]
    assert last_play.pauses_left == 0
    assert runs(ticks)[-3:] == [(Phase.PLAYING, 0), (Phase.PENALTIES, 0), (Phase.FINISHED, 0)]


def test_a_match_that_ends_in_a_draw_without_a_shootout_also_ends_with_0():
    ticks = drain(idle_session(8, countdown=1, pause=1, allow_draws=True))
    assert not any(t.phase is Phase.PENALTIES for t in ticks)
    assert (ticks[-1].phase, ticks[-1].pauses_left) == (Phase.FINISHED, 0)


# --- el payload -------------------------------------------------------------------


def _result(phase, pauses_left, event=None, **kw) -> TickResult:
    state = create_initial_state(make_team().players, make_team(first_id=10).players, 1)
    return TickResult(3, phase, event, state, 0, 0, 5.0, 5.0, 1, pauses_left=pauses_left, **kw)


@pytest.mark.parametrize("pauses_left", [0, 1, 2, 3])
def test_payload_carries_pauses_left_as_an_integer(pauses_left):
    payload = build_tick_payload(_result(Phase.PLAYING, pauses_left), CTX)
    assert payload["pausesLeft"] == pauses_left and type(payload["pausesLeft"]) is int
    TickPayload.model_validate(payload)


def test_every_tick_of_a_full_match_validates_against_the_contract():
    for t in drain(idle_session(8, countdown=1, pause=1, allow_draws=False)):
        payload = build_tick_payload(t, CTX)
        TickPayload.model_validate(payload)  # `pausesLeft` obligatorio, entero de 0 a 3
        assert payload["pausesLeft"] == t.pauses_left


def test_the_key_is_present_in_every_phase():
    kinds = {
        Phase.COUNTDOWN: dict(event=Event.PERIOD_START),
        Phase.PLAYING: {},
        Phase.PAUSED: dict(
            event=Event.PAUSE,
            pause_reason=match_rules.PauseReason.HYDRATION,
            pause_remaining_seconds=15,
            pause_duration_seconds=15,
        ),
    }
    for phase, kw in kinds.items():
        assert "pausesLeft" in build_tick_payload(_result(phase, 2, **kw), CTX)


# --- el loop en tiempo real -------------------------------------------------------


def run(runner):
    async def main():
        await runner.start(1)
        await asyncio.gather(*list(_closing))

    asyncio.run(main())


def stream(**over):
    """El stream completo de ticks de un partido chico, como lo recibe un suscriptor."""
    ws = FakeWs()
    run(build(FakeManager([ws]), FakeMatchRepo(), **{**SMALL, **over}))
    return ws.received


def phase_values(ticks):
    return [k for k, _ in groupby((t["phase"], t["pausesLeft"]) for t in ticks)]


def test_runner_stream_has_the_full_sequence_and_validates():
    ticks = stream()
    assert len(ticks) == SMALL_TOTAL
    for t in ticks:
        TickPayload.model_validate(t)
    assert phase_values(ticks) == [
        ("countdown", 3), ("playing", 3),
        ("paused", 2), ("countdown", 2), ("playing", 2),
        ("paused", 1), ("countdown", 1), ("playing", 1),
        ("paused", 0), ("countdown", 0), ("playing", 0),
        ("finished", 0),
    ]


def test_runner_decrements_on_the_exact_tick_of_the_pause_event():
    ticks = stream()
    starts = [i for i, t in enumerate(ticks) if t["event"] and t["event"]["type"] == "pause"]
    assert len(starts) == 3
    for n, i in enumerate(starts, start=1):
        assert ticks[i]["pausesLeft"] == 3 - n
        assert ticks[i - 1]["pausesLeft"] == 3 - n + 1


def test_runner_with_pauses_of_another_length_keeps_the_same_values():
    assert phase_values(stream(pause_seconds=2)) == phase_values(stream())


def test_a_shootout_through_the_runner_stays_at_0(monkeypatch):
    monkeypatch.setattr(MatchSession, "_goes_to_penalties", lambda self: True)
    ticks = stream(allow_draws=False)
    penalties = [t for t in ticks if t["phase"] == "penalties"]
    assert penalties and ticks[-1]["phase"] == "finished"
    for t in ticks:
        TickPayload.model_validate(t)
    assert {t["pausesLeft"] for t in penalties} == {0}
    assert ticks[-1]["pausesLeft"] == 0
    assert phase_values(ticks)[-3:] == [("playing", 0), ("penalties", 0), ("finished", 0)]


def late_joiners(join_at, *, reconnect=False, **over):
    """Un suscriptor entra con el partido en marcha (sin replay) en cada tick de `join_at`.

    Con `reconnect`, el que estaba conectado se cae justo antes y el nuevo lo reemplaza.
    Devuelve {tick en que entró: primer tick que recibió}.
    """
    first = FakeWs()
    manager = FakeManager([first])
    late: dict[int, FakeWs] = {}
    state = {"current": first, "n": 0}

    def probe(_tick):
        state["n"] += 1  # ticks transmitidos hasta ahora (lo cuenta quien está conectado)
        n = state["n"]
        if n in join_at and n not in late:
            joiner = FakeWs()
            late[n] = joiner
            if reconnect:
                state["current"].closed = (1006, "lost")
                state["current"].probe = None
                joiner.probe = probe
            manager.sockets.append(joiner)
            state["current"] = joiner

    first.probe = probe
    run(build(manager, FakeMatchRepo(), **{**SMALL, **over}))
    return {n: ws.received[0] for n, ws in late.items() if ws.received}


def test_a_late_client_gets_the_right_value_in_its_first_tick_at_every_point_of_the_match():
    reference = stream()
    joined = late_joiners(set(range(1, SMALL_TOTAL)))
    assert set(joined) == set(range(1, SMALL_TOTAL))
    for n, first_tick in joined.items():
        assert first_tick["pausesLeft"] == reference[n]["pausesLeft"], n
        assert first_tick["phase"] == reference[n]["phase"]
        TickPayload.model_validate(first_tick)


@pytest.mark.parametrize(
    ("period", "expected"),
    [(1, 3), (2, 2), (3, 1), (4, 0)],
)
def test_a_late_client_in_each_period_gets_the_value_of_that_period(period, expected):
    reference = stream()
    # a mitad del juego de ese período (el período p arranca en su cuenta regresiva)
    in_play = [i for i, t in enumerate(reference) if t["phase"] == "playing"]
    per_period = [in_play[i * 10:(i + 1) * 10] for i in range(4)]
    n = per_period[period - 1][5]
    first_tick = late_joiners({n})[n]
    assert (first_tick["phase"], first_tick["pausesLeft"]) == ("playing", expected)


def test_a_client_that_joins_in_the_middle_of_a_pause_does_not_count_that_pause():
    reference = stream()
    pauses = [i for i, t in enumerate(reference) if t["phase"] == "paused"]
    middles = {pauses[0] + 10, pauses[20] + 10, pauses[40] + 10}
    joined = late_joiners(middles)
    assert [joined[n]["pausesLeft"] for n in sorted(middles)] == [2, 1, 0]
    assert all(joined[n]["event"] is None for n in middles)  # entró sin ver el `pause`


def test_a_client_that_reconnects_knows_the_value_from_its_first_tick():
    reference = stream()
    points = set(range(1, SMALL_TOTAL, 3))
    joined = late_joiners(points, reconnect=True)
    assert set(joined) == points
    for n, first_tick in joined.items():
        assert first_tick["pausesLeft"] == reference[n]["pausesLeft"], n


def test_players_and_spectators_receive_the_same_value_tick_by_tick():
    player, spectator = FakeWs(), FakeWs()

    class TwoUsers(FakeManager):
        def subscribers(self, match_id):
            return [(ws, uid) for ws, uid in zip(self.sockets, (7, 99)) if ws.closed is None]

    run(build(TwoUsers([player, spectator]), FakeMatchRepo(), **SMALL))
    assert [t["pausesLeft"] for t in player.received] == [t["pausesLeft"] for t in spectator.received]
    assert player.received == spectator.received  # la transmisión es idéntica
    assert {t["pausesLeft"] for t in player.received} == {0, 1, 2, 3}


def test_the_runner_progress_carries_the_same_value_as_the_tick():
    seen = []
    ws = FakeWs()
    manager = FakeManager([ws])
    runner = build(manager, FakeMatchRepo(), **SMALL)
    ws.probe = lambda tick: seen.append((tick["pausesLeft"], runner.progress(1).pauses_left))
    run(runner)
    assert len(seen) == SMALL_TOTAL and all(a == b for a, b in seen)


# --- consistencia con el 409 de las sustituciones ---------------------------------


class Scenario:
    """Un SubstitutionService real mirando el progreso del runner mientras se juega."""

    def __init__(self, repo: FakeMatchRepo, runner: MatchRunner):
        matches = create_autospec(
            AbstractMatchRepository,
            instance=True,
        )
        matches.get_players.side_effect = lambda _id: MatchPlayersData(
            id=1,
            league_id=None,
            status=MatchStatus(repo.states[1].status),
            user_1_id=7,
            user_2_id=8,
        )
        teams = create_autospec(AbstractTeamRepository, instance=True)
        teams.get_team_player_ids.side_effect = (
            lambda _m, _l, _u, *, substitutes: {13, 14, 15} if substitutes else {10, 11, 12}
        )
        teams.get_member_id.side_effect = lambda _m, _l, _u, pid: pid + 100
        substitutions = create_autospec(AbstractSubstitutionRepository, instance=True)
        substitutions.list_by_match.return_value = []
        substitutions.list_applied_by_match.return_value = []
        self.service = SubstitutionService(matches, teams, substitutions, runner)

    def put(self):
        try:
            self.service.request_substitution(7, 1, {"starterId": 10, "substituteId": 13})
            return 204
        except ApiError as exc:
            return (exc.status_code, exc.code)

    def get(self):
        try:
            self.service.get_substitutions(7, 1)
            return 200
        except ApiError as exc:
            return (exc.status_code, exc.code)


def expected_responses(tick, status):
    """Qué deben responder PUT y GET para este tick, según el contrato."""
    paused = tick["phase"] == "paused"
    if status != "started":
        return (409, "matchNotStarted"), (409, "matchNotStarted")
    if tick["phase"] == "penalties":
        return (409, "matchInPenalties"), (409, "matchInPenalties")
    left = tick["pausesLeft"]
    put = 204 if left > 0 else (409, "noPausesLeft")
    # el GET dentro de la última pausa muestra lo aplicado (200); fuera de ella, 409 con 0
    get = 200 if left > 0 or paused else (409, "noPausesLeft")
    return put, get


def audit(**over):
    """Juega el partido y, en cada tick, compara el REST con lo que dice el tick."""
    repo = FakeMatchRepo()
    repo.add(1)
    ws = FakeWs()
    runner = build(FakeManager([ws]), repo, **{**SMALL, **over})
    scenario = Scenario(repo, runner)
    audited = []

    def probe(tick):
        if tick["phase"] == "finished":  # el partido ya se guardó como terminado
            return
        status = repo.states[1].status
        audited.append(
            (tick, status, scenario.put(), scenario.get(), expected_responses(tick, status))
        )

    ws.probe = probe
    run(runner)
    return audited


def test_rest_409_matches_pauses_left_on_every_tick_of_the_match():
    audited = audit()
    assert len(audited) == SMALL_TOTAL - 1
    for tick, status, put, get, (want_put, want_get) in audited:
        where = (tick["phase"], tick["pausesLeft"], status)
        assert put == want_put, where
        assert get == want_get, where


def test_no_pauses_left_is_exactly_pauses_left_equal_0():
    audited = audit()
    for tick, status, put, _get, _ in audited:
        if status == "started" and tick["phase"] != "penalties":
            assert (put == (409, "noPausesLeft")) == (tick["pausesLeft"] == 0)


def test_requests_in_the_first_countdown_are_match_not_started_even_with_3_left():
    audited = audit()
    first_countdown = [a for a in audited if a[0]["phase"] == "countdown" and a[1] != "started"]
    assert first_countdown and all(a[0]["pausesLeft"] == 3 for a in first_countdown)
    assert all(a[2] == a[3] == (409, "matchNotStarted") for a in first_countdown)


def test_each_stretch_of_the_match_has_the_expected_rest_answer():
    seen = {}
    for tick, status, put, get, _ in audit():
        seen.setdefault((tick["phase"], tick["pausesLeft"], status), (put, get))
    started = "started"
    assert seen[("playing", 3, started)] == (204, 200)  # período 1
    assert seen[("paused", 2, started)] == (204, 200)  # 1.ª pausa: queda pendiente la siguiente
    assert seen[("countdown", 2, started)] == (204, 200)
    assert seen[("playing", 2, started)] == (204, 200)
    assert seen[("paused", 1, started)] == (204, 200)  # 2.ª pausa
    assert seen[("playing", 1, started)] == (204, 200)
    assert seen[("paused", 0, started)] == ((409, "noPausesLeft"), 200)  # última pausa
    assert seen[("countdown", 0, started)] == ((409, "noPausesLeft"),) * 2
    assert seen[("playing", 0, started)] == ((409, "noPausesLeft"),) * 2  # período 4


def test_rest_during_the_shootout_is_in_penalties_and_not_no_pauses_left(monkeypatch):
    monkeypatch.setattr(MatchSession, "_goes_to_penalties", lambda self: True)
    audited = audit(allow_draws=False)
    penalties = [a for a in audited if a[0]["phase"] == "penalties"]
    assert penalties
    for tick, _status, put, get, _ in penalties:
        assert tick["pausesLeft"] == 0
        assert put == get == (409, "matchInPenalties")
    # el último tick de juego (período 4) sigue siendo noPausesLeft
    last_play = [a for a in audited if a[0]["phase"] == "playing"][-1]
    assert last_play[2] == (409, "noPausesLeft")


def test_a_league_style_schedule_keeps_rest_and_ticks_consistent():
    for tick, status, put, get, (want_put, want_get) in audit(pause_seconds=2, duration=4):
        assert (put, get) == (want_put, want_get), (tick["phase"], tick["pausesLeft"], status)


def test_a_match_that_is_not_played_in_this_process_has_no_pause_to_apply():
    repo = FakeMatchRepo()
    repo.add(1, MatchStatus.started)
    runner = build(FakeManager([]), repo, **SMALL)  # nunca se arrancó
    scenario = Scenario(repo, runner)
    assert scenario.put() == (409, "noPausesLeft")


# --- una sola implementación de la regla ------------------------------------------


@pytest.mark.parametrize(
    ("period", "pauses_left", "put"),
    [
        (1, 0, (409, "noPausesLeft")),  # el valor manda aunque `period` diga que quedan pausas
        (4, 2, 204),  # y a la inversa: no se recalcula desde `period` y `periods`
        (2, 2, 204),
        (3, 0, (409, "noPausesLeft")),
    ],
)
def test_the_409_reads_pauses_left_and_does_not_recompute_it(period, pauses_left, put):
    repo = FakeMatchRepo()
    repo.add(1, MatchStatus.started)

    class Reader:
        def progress(self, _id):
            return MatchProgress(Phase.PLAYING, period, 4, pauses_left)

    scenario = Scenario(repo, Reader())
    assert scenario.put() == put
    assert scenario.get() == (200 if pauses_left > 0 else (409, "noPausesLeft"))
