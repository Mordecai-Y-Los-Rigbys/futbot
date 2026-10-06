import pytest

from app.simulation.actions import GoTo, Kick, KickTo, MoveInDirection
from app.simulation.behaviors.primitives import (
    ActionRecorder,
    BehaviorError,
    MatchClock,
    behavior_constants,
    build_primitives,
)
from app.simulation.constants import FIELD_LENGTH, FIELD_WIDTH, MAX_KICK_FORCE
from app.tests.unit.simulation_helpers import AWAY, HOME, player, state

CLOCK = MatchClock(elapsed=30.0, remaining=150.0)


def match(owner=None):
    """Local 1 en (20, 10), local 2 en (30, 40), visitante 3 en (70, 15).
    Pelota en (50, 30)."""
    return state(
        player(HOME, 1, x=20.0, y=10.0, power=40),
        player(HOME, 2, x=30.0, y=40.0),
        player(AWAY, 3, x=70.0, y=15.0, speed=90),
        ball=(50.0, 30.0),
        owner=owner,
    )


def primitives_for(key, s=None, clock=CLOCK):
    recorder = ActionRecorder()
    return build_primitives(s or match(), key, clock, recorder), recorder


def mirrored(x, y):
    return (FIELD_LENGTH - x, FIELD_WIDTH - y)


# --- lectura en coordenadas relativas -----------------------------------------


def test_home_reads_absolute_positions():
    p, _ = primitives_for((HOME, 1))
    assert p["my_position"]() == (20.0, 10.0)
    assert p["ball_position"]() == (50.0, 30.0)
    assert p["teammate_position"](2) == (30.0, 40.0)
    assert p["opponent_position"](3) == (70.0, 15.0)


def test_away_reads_the_field_rotated():
    p, _ = primitives_for((AWAY, 3))
    assert p["my_position"]() == mirrored(70.0, 15.0)
    assert p["ball_position"]() == mirrored(50.0, 30.0)
    assert p["opponent_position"](1) == mirrored(20.0, 10.0)


def test_my_number_is_tied_to_the_role():
    p, _ = primitives_for((AWAY, 3))
    assert p["my_number"]() == 3


def test_stats_of_teammates_and_opponents():
    p, _ = primitives_for((HOME, 2))
    assert p["teammate_stat"](1, "power") == 40
    assert p["opponent_stat"](3, "speed") == 90


@pytest.mark.parametrize("num", [0, 4, -1, 1.0, "1", True, None])
def test_invalid_player_number_raises(num):
    p, _ = primitives_for((HOME, 1))
    with pytest.raises(BehaviorError):
        p["teammate_position"](num)


def test_invalid_stat_raises():
    p, _ = primitives_for((HOME, 1))
    with pytest.raises(BehaviorError):
        p["teammate_stat"](1, "magic")


# --- quién tiene la pelota ----------------------------------------------------


@pytest.mark.parametrize(
    "owner, me, expected",
    [
        (None, (HOME, 1), (False, False, False, True)),
        ((HOME, 1), (HOME, 1), (True, False, False, False)),
        ((HOME, 2), (HOME, 1), (False, True, False, False)),
        ((AWAY, 3), (HOME, 1), (False, False, True, False)),
        ((HOME, 1), (AWAY, 3), (False, False, True, False)),
    ],
)
def test_who_has_the_ball(owner, me, expected):
    p, _ = primitives_for(me, match(owner=owner))
    got = (
        p["i_have_ball"](),
        p["teammate_has_ball"](),
        p["opponent_has_ball"](),
        p["nobody_has_ball"](),
    )
    assert got == expected


# --- acciones -----------------------------------------------------------------


def test_go_to_is_recorded_in_absolute_coordinates():
    p, home = primitives_for((HOME, 1))
    p["go_to"](10, 5)
    assert home.move == GoTo(10.0, 5.0)

    p, away = primitives_for((AWAY, 3))
    p["go_to"](10, 5)
    assert away.move == GoTo(*mirrored(10.0, 5.0))


def test_move_in_direction_is_inverted_for_away():
    p, home = primitives_for((HOME, 1))
    p["move_in_direction"](1, 0.5)
    assert home.move == MoveInDirection(1.0, 0.5)

    p, away = primitives_for((AWAY, 3))
    p["move_in_direction"](1, 0.5)
    assert away.move == MoveInDirection(-1.0, -0.5)


def test_kicks_default_to_full_force():
    p, recorder = primitives_for((HOME, 1))
    p["kick"]()
    assert recorder.kick == Kick(force=MAX_KICK_FORCE)

    p["kick_to"](100, 30)
    assert recorder.kick == KickTo(100.0, 30.0, force=MAX_KICK_FORCE)


def test_kick_to_is_recorded_in_absolute_coordinates_for_away():
    p, recorder = primitives_for((AWAY, 3))
    p["kick_to"](100, 30, force=50)
    assert recorder.kick == KickTo(*mirrored(100.0, 30.0), force=50)


def test_the_last_action_of_each_kind_wins():
    p, recorder = primitives_for((HOME, 1))
    p["go_to"](1, 1)
    p["move_in_direction"](0, 1)
    p["kick"](10)
    p["kick_to"](5, 5)
    assert recorder.move == MoveInDirection(0.0, 1.0)
    assert recorder.kick == KickTo(5.0, 5.0, force=MAX_KICK_FORCE)


def test_recorder_starts_empty():
    _, recorder = primitives_for((HOME, 1))
    actions = recorder.actions()
    assert actions.move is None and actions.kick is None


@pytest.mark.parametrize("bad", ["10", None, True, float("inf"), float("nan"), (1, 2)])
def test_actions_reject_anything_that_is_not_a_finite_number(bad):
    p, recorder = primitives_for((HOME, 1))
    with pytest.raises(BehaviorError):
        p["go_to"](bad, 5)
    with pytest.raises(BehaviorError):
        p["kick"](bad)
    assert recorder.move is None and recorder.kick is None


# --- utilidades, tiempo y constantes ------------------------------------------


def test_distance():
    p, _ = primitives_for((HOME, 1))
    assert p["distance"](0, 0, 3, 4) == pytest.approx(5.0)


def test_time_comes_from_the_match_clock():
    p, _ = primitives_for((HOME, 1), clock=MatchClock(elapsed=12.5, remaining=167.5))
    assert p["elapsed_time"]() == 12.5
    assert p["remaining_time"]() == 167.5
    assert p["current_period"]() == 1


def test_constants_are_relative_to_the_own_team():
    constants = behavior_constants()
    assert constants["my_goal"] == (0.0, FIELD_WIDTH / 2)
    assert constants["opponent_goal"] == (FIELD_LENGTH, FIELD_WIDTH / 2)
    assert constants["top_right_corner"] == (FIELD_LENGTH, FIELD_WIDTH)
