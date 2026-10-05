import copy
import time

import pytest

from app.simulation import constants as C
from app.simulation import match_rules
from app.simulation.geometry import Vec
from app.simulation.match_rules import Event, Phase, build_session
from app.simulation.physics import create_initial_state
from app.simulation.simulate import simulate_match
from app.simulation.state import Goal, StepResult, Team
from app.simulation.run import default_team as make_team

CT = round(C.COUNTDOWN_SECONDS * C.TICKS_PER_SECOND)


def test_duration_is_play_ticks_plus_countdown():
    result = simulate_match(make_team(), make_team(first_id=10), 5, seed=1)
    assert len(result.ticks) == CT + 5 * C.TICKS_PER_SECOND


def test_sequence_countdown_playing_finished():
    ticks = simulate_match(make_team(), make_team(first_id=10), 5, seed=1).ticks
    assert (ticks[0].phase, ticks[0].event) == (Phase.COUNTDOWN, Event.PERIOD_START)
    assert all(t.phase is Phase.COUNTDOWN for t in ticks[:CT])
    assert all(t.event is None for t in ticks[1:CT])
    assert ticks[CT].phase is Phase.PLAYING
    assert (ticks[-1].phase, ticks[-1].event) == (Phase.FINISHED, Event.MATCH_END)
    assert sum(t.phase is Phase.FINISHED for t in ticks) == 1
    assert [t.tick for t in ticks] == list(range(len(ticks)))


def test_clock_does_not_run_during_countdown():
    ticks = simulate_match(make_team(), make_team(first_id=10), 5, seed=1).ticks
    assert all(t.elapsed == 0 for t in ticks[:CT])
    assert ticks[CT].elapsed == pytest.approx(C.SECONDS_PER_TICK)
    assert ticks[-1].remaining == pytest.approx(0)


def test_seed_goes_to_the_initial_state():
    ticks = simulate_match(make_team(), make_team(first_id=10), 1, seed=99).ticks
    assert ticks[0].state.seed == 99


def test_goal_then_everyone_back_to_start_and_clock_keeps_running(monkeypatch):
    calls = {"n": 0}

    def fake_step(state, actions):
        calls["n"] += 1
        new = copy.deepcopy(state)
        new.tick += 1
        new.players[0].position = Vec(5.0, 5.0)
        new.ball.position = Vec(101.0, 30.0)  # adentro del arco
        events = (Goal(Team.HOME),) if calls["n"] == 3 else ()
        return StepResult(new, events)

    monkeypatch.setattr(match_rules, "step", fake_step)
    team_1, team_2 = make_team(), make_team(first_id=10)
    session = build_session(team_1, team_2, 1, seed=5, countdown_seconds=0)
    ticks = [session.advance() for _ in range(5)]

    goal, after = ticks[2], ticks[3]
    assert (goal.event, goal.score_1, goal.score_2) == (Event.GOAL, 1, 0)
    assert goal.scoring_team is Team.HOME
    assert goal.state.ball.position.x > C.FIELD_LENGTH  # el tick del gol muestra la pelota adentro
    initial = create_initial_state(team_1.players, team_2.players, 5)
    assert [p.position for p in after.state.players] == [p.position for p in initial.players]
    assert after.state.ball.position == initial.ball.position
    assert after.state.ball.owner is None
    assert after.state.ball.velocity == initial.ball.velocity
    assert after.event is None and after.phase is Phase.PLAYING
    assert after.elapsed > goal.elapsed  # el reloj no se detuvo
    assert calls["n"] == 4  # 5 ticks, el del reacomodo no corre la física


def test_same_seed_same_ticks():
    a = simulate_match(make_team(), make_team(first_id=10), 5, seed=3)
    b = simulate_match(make_team(), make_team(first_id=10), 5, seed=3)
    assert a == b


def test_identical_teams_play_mirrored_until_the_first_tiebreak():
    ticks = simulate_match(
        make_team(), make_team(first_id=10), 3, seed=1, countdown_seconds=0.5
    ).ticks
    compared = 0
    for t in ticks:
        if t.state.ball.owner is not None:  # primer desempate: acá se rompe la simetría
            break
        pos = {p.key: p.position for p in t.state.players}
        for num in (1, 2, 3):
            team_1, team_2 = pos[(Team.HOME, num)], pos[(Team.AWAY, num)]
            assert (team_2.x, team_2.y) == pytest.approx(
                (C.FIELD_LENGTH - team_1.x, C.FIELD_WIDTH - team_1.y)
            )
        compared += 1
    assert compared > 5


def test_each_tick_takes_less_than_100ms():
    session = build_session(make_team(), make_team(first_id=10), 10, seed=1, countdown_seconds=0)
    worst = 0.0
    for _ in range(200):
        began = time.perf_counter()
        session.advance()
        worst = max(worst, time.perf_counter() - began)
    assert worst < 0.1