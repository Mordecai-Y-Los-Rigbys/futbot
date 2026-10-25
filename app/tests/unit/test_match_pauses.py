"""Pausas, cuenta regresiva reiniciada y reloj de MatchSession (4 períodos)."""

import copy

import pytest

from app.simulation import constants as C
from app.simulation import match_rules
from app.simulation.actions import GoTo
from app.simulation.geometry import Vec
from app.simulation.match_rules import Event, PauseReason, Phase, build_session
from app.simulation.physics import create_initial_state
from app.simulation.run import default_team as make_team
from app.simulation.simulate import simulate_match
from app.simulation.state import Goal, StepResult, Team

SEED = 1


def make(duration=8, countdown=1, pause=1, periods=4):
    """Sesión chica: 8 s de juego en 4 períodos de 2 s, pausas y cuentas de 1 s."""
    t1, t2 = make_team(), make_team(first_id=10)
    session = build_session(t1, t2, duration, SEED, countdown, periods, pause)
    return session, create_initial_state(t1.players, t2.players, SEED)


def drain(session):
    ticks = []
    while not session.finished:
        ticks.append(session.advance())
    return ticks


def index_of(ticks, tick):
    return next(i for i, t in enumerate(ticks) if t is tick)


# --- cuándo empieza cada pausa ------------------------------------------------


@pytest.mark.parametrize(
    "duration, expected",
    [
        (60, [15.0, 30.0, 45.0]),  # liga de 1 minuto
        (600, [150.0, 300.0, 450.0]),  # liga de 10 minutos
        (C.FRIENDLY_MATCH_DURATION * 60, [45.0, 90.0, 135.0]),  # amistoso: 0:45, 1:30, 2:15
    ],
)
def test_pauses_start_at_quarters_of_the_match(duration, expected):
    session, _ = make(duration, pause=C.PAUSE_SECONDS, countdown=C.COUNTDOWN_SECONDS)
    assert session.pause_starts == expected


def test_first_tick_of_each_pause_carries_the_pause_event():
    session, _ = make()
    firsts = [t for t in drain(session) if t.event is Event.PAUSE]
    assert [t.elapsed for t in firsts] == [2.0, 4.0, 6.0]
    assert [t.pause_reason for t in firsts] == [
        PauseReason.HYDRATION,
        PauseReason.HALFTIME,
        PauseReason.HYDRATION,
    ]
    assert all(t.phase is Phase.PAUSED and t.pause_duration_seconds == 1 for t in firsts)


def test_only_pause_ticks_carry_pause_fields():
    session, _ = make()
    for t in drain(session):
        if t.phase is Phase.PAUSED:
            assert t.pause_remaining_seconds is not None
            assert t.pause_reason is not None
        else:
            assert t.pause_remaining_seconds is None
            assert t.pause_reason is None
            assert t.pause_duration_seconds is None


def test_total_ticks_with_default_constants():
    session, _ = make(180, pause=C.PAUSE_SECONDS, countdown=C.COUNTDOWN_SECONDS)
    expected = 100 + 3600 + 3 * (300 + 100)
    assert session.total_ticks == expected


# --- la pausa congela todo ----------------------------------------------------


def test_pause_and_countdown_freeze_clock_state_and_behaviors(monkeypatch):
    calls = {"n": 0}
    real = match_rules.run_behaviors

    def spy(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(match_rules, "run_behaviors", spy)
    session, _ = make()
    ticks = []
    while not session.finished:
        before = calls["n"]
        tick = session.advance()
        if tick.phase in (Phase.PAUSED, Phase.COUNTDOWN):
            assert calls["n"] == before  # los behaviors no corren
        ticks.append(tick)

    for period in (1, 2, 3):
        pause = [t for t in ticks if t.phase is Phase.PAUSED and t.period == period]
        assert len(pause) == 20
        assert all(t.state == pause[0].state for t in pause)
        assert all(t.elapsed == pause[0].elapsed for t in pause)
        assert all(t.remaining == pause[0].remaining for t in pause)
        last_playing = ticks[index_of(ticks, pause[0]) - 1]
        assert last_playing.state == pause[0].state  # el estado con el que empezó la pausa

    for period in (1, 2, 3, 4):
        cd = [t for t in ticks if t.phase is Phase.COUNTDOWN and t.period == period]
        assert len(cd) == 20
        assert all(t.state == cd[0].state for t in cd)
        assert all(t.elapsed == cd[0].elapsed for t in cd)


def test_pause_remaining_goes_from_15_to_0_then_countdown_of_the_next_period():
    session, _ = make(8, countdown=5, pause=15)
    ticks = drain(session)
    pause = [t for t in ticks if t.phase is Phase.PAUSED and t.period == 1]
    values = [t.pause_remaining_seconds for t in pause]
    assert len(pause) == 300
    assert values[0] == 15 and values[-1] == 0
    assert values == sorted(values, reverse=True)
    assert set(values) == set(range(16))  # baja de a un segundo, sin saltos
    after = ticks[index_of(ticks, pause[-1]) + 1 :][:100]
    assert all(t.phase is Phase.COUNTDOWN and t.period == 2 for t in after)
    assert after[0].event is Event.PERIOD_START
    assert all(t.event is None for t in after[1:])


def test_period_start_of_every_period():
    session, _ = make()
    starts = [(t.event, t.period) for t in drain(session) if t.event is Event.PERIOD_START]
    assert starts == [(Event.PERIOD_START, p) for p in (1, 2, 3, 4)]


# --- reinicio como saque normal -----------------------------------------------


@pytest.mark.parametrize("pending_goal", [False, True])
def test_countdown_after_a_pause_restarts_as_a_normal_kickoff(pending_goal):
    session, initial = make()
    while session.advance().phase is not Phase.PAUSED:
        pass
    # Ensucia el estado: pelota en movimiento, cooldowns, movimientos previos.
    s = session._state
    s.ball.velocity, s.ball.owner, s.ball.position = Vec(30.0, 5.0), (Team.HOME, 3), Vec(70.0, 10.0)
    for p in s.players:
        p.move, p.next_kick_tick, p.regain_blocked_until = GoTo(10.0, 10.0), 999, 999
        p.position = Vec(20.0, 20.0)
    session._pending_reset = pending_goal

    frozen = session.advance()  # sigue en pausa, con el estado tal cual estaba
    assert frozen.phase is Phase.PAUSED and frozen.state.ball.velocity == Vec(30.0, 5.0)

    tick = session.advance()
    while tick.phase is Phase.PAUSED:
        tick = session.advance()

    assert tick.phase is Phase.COUNTDOWN and tick.event is Event.PERIOD_START and tick.period == 2
    assert [p.position for p in tick.state.players] == [p.position for p in initial.players]
    assert tick.state.ball == initial.ball  # centro, sin velocidad ni dueño
    assert all(
        p.move is None
        and p.next_kick_tick == C.NO_KICK_COOLDOWN
        and p.regain_blocked_until == C.NOT_REGAIN_BLOCKED
        for p in tick.state.players
    )
    assert session._pending_reset is False


def test_positions_do_not_change_during_the_restarted_countdown():
    session, initial = make()
    ticks = drain(session)
    for period in (2, 3, 4):
        cd = [t for t in ticks if t.phase is Phase.COUNTDOWN and t.period == period]
        assert all(
            [p.position for p in t.state.players] == [p.position for p in initial.players]
            for t in cd
        )
        assert all(t.state.ball == initial.ball for t in cd)


def test_restart_also_happens_without_countdown():
    session, initial = make(countdown=0)
    while session.advance().phase is not Phase.PAUSED:
        pass
    session._state.ball.velocity = Vec(30.0, 5.0)
    tick = session.advance()
    while tick.phase is Phase.PAUSED:
        tick = session.advance()
    assert tick.phase is Phase.PLAYING
    assert tick.state.ball.velocity == Vec(0.0, 0.0)  # sin la velocidad previa


def test_goal_in_the_last_tick_of_a_period_resets_positions_in_the_first_pause_tick(monkeypatch):
    calls = {"n": 0}

    def fake_step(state, actions):
        calls["n"] += 1
        new = copy.deepcopy(state)
        new.tick += 1
        new.players[0].position = Vec(5.0, 5.0)
        if calls["n"] == 40:  # último tick de juego del período 1 (8 s / 4 = 2 s = 40 ticks)
            new.ball.position = Vec(101.0, 30.0)  # adentro del arco
            return StepResult(new, (Goal(Team.HOME),))
        return StepResult(new)

    monkeypatch.setattr(match_rules, "step", fake_step)
    session, initial = make()
    ticks = drain(session)

    goal_index = next(i for i, t in enumerate(ticks) if t.event is Event.GOAL)
    goal, first_pause = ticks[goal_index], ticks[goal_index + 1]
    assert goal.state.ball.position.x > C.FIELD_LENGTH  # el tick del gol muestra la pelota adentro
    assert first_pause.phase is Phase.PAUSED and first_pause.event is Event.PAUSE
    assert first_pause.score_1 == 1
    assert [p.position for p in first_pause.state.players] == [p.position for p in initial.players]
    assert first_pause.state.ball == initial.ball

    pause = [t for t in ticks if t.phase is Phase.PAUSED and t.period == 1]
    assert all(t.state == first_pause.state for t in pause)  # congelado en el estado ya reiniciado


# --- reloj ---------------------------------------------------------------------


def test_clock_counts_only_play_time():
    ticks = simulate_match(make_team(), make_team(first_id=10), 8, SEED, 1, 4, 1).ticks
    assert ticks[-1].elapsed == 8.0 and ticks[-1].remaining == pytest.approx(0)
    assert sum(t.phase in (Phase.PLAYING, Phase.FINISHED) for t in ticks) == 160


@pytest.mark.slow
def test_friendly_of_3_minutes_end_to_end():
    ticks = simulate_match(make_team(), make_team(first_id=10), 180, SEED).ticks
    assert [t.elapsed for t in ticks if t.event is Event.PAUSE] == [45.0, 90.0, 135.0]
    pauses = [t for t in ticks if t.phase is Phase.PAUSED]
    assert len(pauses) == 3 * 300
    assert [t.pause_remaining_seconds for t in pauses[:300]][0] == 15
    assert pauses[299].pause_remaining_seconds == 0
    assert sum(t.phase in (Phase.PLAYING, Phase.FINISHED) for t in ticks) == 3600
    assert ticks[-1].elapsed == 180.0 and ticks[-1].phase is Phase.FINISHED
    assert len(ticks) == 100 + 3600 + 3 * (300 + 100)