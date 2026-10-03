import pytest

from app.simulation.actions import GoTo, MoveInDirection, PlayerActions
from app.simulation.constants import FIELD_LENGTH, FIELD_WIDTH, PLAYER_RADIUS, TICKS_PER_SECOND
from app.simulation.physics import player_speed, step
from app.tests.unit.simulation_helpers import HOME, player, run, state

KEY = (HOME, 1)


def move(dx, dy):
    return {KEY: PlayerActions(move=MoveInDirection(dx, dy))}


def go_to(x, y):
    return {KEY: PlayerActions(move=GoTo(x, y))}


@pytest.mark.parametrize("speed, expected", [(20, 8.0), (60, 14.0), (100, 20.0)])
def test_distance_in_one_second_follows_the_speed_formula(speed, expected):
    assert player_speed(speed) == pytest.approx(expected)
    s, _ = run(state(player(x=10.0, speed=speed)), TICKS_PER_SECOND, move(1, 0))
    assert s.player(KEY).position.x == pytest.approx(10.0 + expected)
    assert s.player(KEY).position.y == pytest.approx(30.0)


def test_direction_is_normalized_regardless_of_its_size():
    a, _ = run(state(player(x=20.0)), 5, move(3, 1))
    b, _ = run(state(player(x=20.0)), 5, move(6, 2))
    c, _ = run(state(player(x=20.0)), 5, move(0.3, 0.1))
    assert a.player(KEY).position == b.player(KEY).position == c.player(KEY).position


def test_diagonal_moves_at_the_same_speed_as_straight():
    s, _ = run(state(player(x=20.0, y=20.0)), TICKS_PER_SECOND, move(1, 1))
    moved = s.player(KEY).position - player(x=20.0, y=20.0).position
    assert moved.length() == pytest.approx(player_speed(60))


def test_zero_direction_stays_still():
    s, _ = run(state(player(x=20.0)), 10, move(0, 0))
    assert s.player(KEY).position == player(x=20.0).position


def test_go_to_does_not_overshoot_the_target():
    # Le falta menos de un tick de recorrido (0,7 u por tick con speed 60).
    s = step(state(player(x=50.0)), go_to(50.3, 30.0)).state
    assert s.player(KEY).position.x == pytest.approx(50.3)

    s, _ = run(s, 10, go_to(50.3, 30.0))
    assert s.player(KEY).position.x == pytest.approx(50.3)


def test_go_to_arrives_and_stops():
    s, _ = run(state(player(x=10.0, y=10.0)), 200, go_to(30.0, 40.0))
    assert s.player(KEY).position.x == pytest.approx(30.0)
    assert s.player(KEY).position.y == pytest.approx(40.0)


@pytest.mark.parametrize(
    "start, direction, expected",
    [
        ((5.0, 30.0), (-1, 0), (PLAYER_RADIUS, 30.0)),
        ((95.0, 30.0), (1, 0), (FIELD_LENGTH - PLAYER_RADIUS, 30.0)),
        ((50.0, 5.0), (0, -1), (50.0, PLAYER_RADIUS)),
        ((50.0, 55.0), (0, 1), (50.0, FIELD_WIDTH - PLAYER_RADIUS)),
    ],
)
def test_player_stops_at_the_border(start, direction, expected):
    s, _ = run(state(player(x=start[0], y=start[1])), 2 * TICKS_PER_SECOND, move(*direction))
    assert s.player(KEY).position.x == pytest.approx(expected[0])
    assert s.player(KEY).position.y == pytest.approx(expected[1])


def test_go_to_outside_the_field_is_clamped():
    s, _ = run(state(player(x=50.0)), 400, go_to(-10.0, 999.0))
    assert s.player(KEY).position.x == pytest.approx(PLAYER_RADIUS)
    assert s.player(KEY).position.y == pytest.approx(FIELD_WIDTH - PLAYER_RADIUS)


def test_last_movement_persists_without_a_new_action():
    s = step(state(player(x=20.0)), move(1, 0)).state
    x_after_first = s.player(KEY).position.x
    s, _ = run(s, 5)  # sin acciones
    assert s.player(KEY).position.x == pytest.approx(x_after_first + 5 * player_speed(60) / TICKS_PER_SECOND)


def test_facing_follows_the_movement():
    s = step(state(player(x=50.0)), move(0, -1)).state
    assert s.player(KEY).facing.y == pytest.approx(-1.0)
