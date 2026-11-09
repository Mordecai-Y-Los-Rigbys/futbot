"""Reglas de la prueba de un comportamiento: un jugador solo, sin rival ni pausas."""

import copy

import pytest

from app.simulation import constants as C
from app.simulation import match_rules
from app.simulation.behavior_test_rules import (
    TEST_PLAYER_KEY,
    BehaviorTestEvent,
    BehaviorTestSession,
)
from app.simulation.behaviors.default_behaviors import FORWARD_CODE
from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.geometry import Vec
from app.simulation.match_rules import Phase
from app.simulation.state import Goal, StepResult, Team

COUNTDOWN_TICKS = C.BEHAVIOR_TEST_COUNTDOWN_SECONDS * C.TICKS_PER_SECOND
PLAYER_START = Vec(40.0, 30.0)  # posición inicial del delantero
FIELD_CENTER = Vec(50.0, 30.0)

# Va a buscar la pelota y, cuando la tiene, la lleva hasta su propio arco.
OWN_GOAL_CODE = """\
ball = ball_position()
if i_have_ball():
    go_to(0, field_width / 2)
else:
    go_to(ball[0], ball[1])
"""


def play(code, **overrides):
    """Corre la prueba completa y devuelve todos sus ticks. Sin `overrides`,
    con la duración y la cuenta regresiva de la prueba."""
    session = BehaviorTestSession(compile_behavior(code), **overrides)
    ticks = []
    while not session.finished:
        ticks.append(session.advance())
    return ticks


def player_position(tick):
    return tick.state.player(TEST_PLAYER_KEY).position


# --- countdown ----------------------------------------------------------------


def test_countdown_of_3_seconds_with_test_start_and_the_player_still():
    ticks = play("go_to(0, 0)", duration_seconds=1)
    countdown = ticks[:COUNTDOWN_TICKS]

    assert (ticks[0].phase, ticks[0].event) == (Phase.COUNTDOWN, BehaviorTestEvent.TEST_START)
    assert all(tick.phase is Phase.COUNTDOWN for tick in countdown)
    assert all(tick.event is None for tick in countdown[1:])
    assert all(player_position(tick) == PLAYER_START for tick in countdown)
    assert all(tick.elapsed == 0 for tick in countdown)
    assert ticks[COUNTDOWN_TICKS].phase is Phase.PLAYING
    assert player_position(ticks[COUNTDOWN_TICKS]) != PLAYER_START  # ya corre el behavior


# --- fin por tiempo -----------------------------------------------------------


def test_ends_by_time_after_60_seconds_of_play():
    ticks = play("go_to(0, 0)")

    assert len(ticks) == COUNTDOWN_TICKS + 60 * C.TICKS_PER_SECOND
    assert (ticks[-1].phase, ticks[-1].event) == (Phase.FINISHED, BehaviorTestEvent.TEST_END)
    assert ticks[-1].elapsed == pytest.approx(60)
    assert all(tick.phase is not Phase.FINISHED for tick in ticks[:-1])


def test_a_goal_on_the_last_tick_ends_with_test_end_and_still_counts(monkeypatch):
    def always_goal(state, actions):
        return StepResult(copy.deepcopy(state), (Goal(Team.HOME),))

    monkeypatch.setattr(match_rules, "step", always_goal)
    ticks = play("go_to(0, 0)", duration_seconds=0.15, countdown_seconds=0)  # gol, reacomodo, gol

    events = [tick.event for tick in ticks]
    assert events == [BehaviorTestEvent.GOAL, None, BehaviorTestEvent.TEST_END]
    assert ticks[-1].goals == 2


# --- goles --------------------------------------------------------------------


def test_goal_counts_and_next_tick_the_player_and_the_ball_are_back_at_the_start():
    ticks = play(FORWARD_CODE)
    goal_indexes = [
        index for index, tick in enumerate(ticks) if tick.event is BehaviorTestEvent.GOAL
    ]
    first_goal, after = ticks[goal_indexes[0]], ticks[goal_indexes[0] + 1]

    assert (ticks[goal_indexes[0] - 1].goals, first_goal.goals) == (0, 1)
    assert first_goal.state.ball.position.x > C.FIELD_LENGTH  # el tick del gol la muestra adentro
    assert player_position(after) == PLAYER_START
    assert (after.state.ball.position, after.state.ball.owner) == (FIELD_CENTER, None)
    assert (after.phase, after.event) == (Phase.PLAYING, None)
    assert after.elapsed > first_goal.elapsed  # el reloj sigue corriendo
    assert ticks[-1].goals == len(goal_indexes) > 1  # la prueba sigue y los goles se acumulan


def test_own_goal_does_not_count_but_resets_the_positions():
    ticks = play(OWN_GOAL_CODE, duration_seconds=20)
    own_goal = next(index for index, tick in enumerate(ticks) if tick.state.ball.position.x < 0)
    after = ticks[own_goal + 1]

    assert player_position(after) == PLAYER_START
    assert after.state.ball.position == FIELD_CENTER
    assert all(tick.goals == 0 for tick in ticks)
    assert all(tick.event is not BehaviorTestEvent.GOAL for tick in ticks)


# --- el behavior --------------------------------------------------------------


def test_the_player_is_club1_and_attacks_toward_x_100():
    ticks = play("go_to(opponent_goal[0], opponent_goal[1])", duration_seconds=1)

    assert [player.key for player in ticks[-1].state.players] == [TEST_PLAYER_KEY]
    assert player_position(ticks[-1]).x > PLAYER_START.x


@pytest.mark.parametrize(
    "call",
    [
        "teammate_position(1)",
        "opponent_position(3)",
        "teammate_stat(2, 'speed')",
        "opponent_stat(1, 'power')",
    ],
)
def test_asking_for_a_player_that_is_not_there_only_discards_that_tick(call):
    code = f"""\
if elapsed_time() < 1:
    go_to(0, 0)
else:
    {call}
    go_to(100, 60)
"""
    ticks = play(code, duration_seconds=2)
    after_one_second = player_position(ticks[COUNTDOWN_TICKS + C.TICKS_PER_SECOND])

    # Siguió hacia (0, 0), su último movimiento: el go_to(100, 60) se descartó.
    assert player_position(ticks[-1]).x < after_one_second.x
    assert ticks[-1].event is BehaviorTestEvent.TEST_END
