import pytest

from app.simulation.constants import (
    BALL_FRICTION_PER_TICK,
    BALL_RADIUS,
    FIELD_LENGTH,
    FIELD_WIDTH,
    GOAL_Y_MAX,
    GOAL_Y_MIN,
    WALL_RESTITUTION,
)
from app.simulation.geometry import ZERO
from app.simulation.physics import step
from app.simulation.state import Goal
from app.tests.unit.simulation_helpers import AWAY, HOME, run, state

BOUNCED = 40 * WALL_RESTITUTION * BALL_FRICTION_PER_TICK


def ball_after_one_tick(position, velocity):
    result = step(state(ball=position, velocity=velocity))
    return result.state.ball, result.events


@pytest.mark.parametrize(
    "position, velocity, expected_velocity",
    [
        ((50.0, 2.0), (0.0, -40.0), (0.0, BOUNCED)),  # abajo
        ((50.0, 58.0), (0.0, 40.0), (0.0, -BOUNCED)),  # arriba
        ((2.0, 10.0), (-40.0, 0.0), (BOUNCED, 0.0)),  # fondo izquierdo, fuera del arco
        ((98.0, 10.0), (40.0, 0.0), (-BOUNCED, 0.0)),  # fondo derecho, fuera del arco
        ((2.0, 2.0), (-40.0, -40.0), (BOUNCED, BOUNCED)),  # esquina
    ],
)
def test_ball_bounces_on_every_border(position, velocity, expected_velocity):
    ball, events = ball_after_one_tick(position, velocity)
    assert not events
    assert ball.velocity.x == pytest.approx(expected_velocity[0])
    assert ball.velocity.y == pytest.approx(expected_velocity[1])
    assert BALL_RADIUS <= ball.position.x <= FIELD_LENGTH - BALL_RADIUS
    assert BALL_RADIUS <= ball.position.y <= FIELD_WIDTH - BALL_RADIUS


@pytest.mark.parametrize(
    "position, velocity, scorer",
    [
        ((2.0, 30.0), (-40.0, 0.0), AWAY),  # entra en el arco del local
        ((98.0, 30.0), (40.0, 0.0), HOME),  # entra en el arco del visitante
        ((2.0, GOAL_Y_MIN + 0.1), (-40.0, 0.0), AWAY),  # rozando un palo
        ((98.0, GOAL_Y_MAX - 0.1), (40.0, 0.0), HOME),
    ],
)
def test_ball_crossing_the_goal_goal_line_is_a_goal(position, velocity, scorer):
    ball, events = ball_after_one_tick(position, velocity)
    assert list(events) == [Goal(scoring_team=scorer)]
    assert ball.velocity == ZERO


@pytest.mark.parametrize("y", [GOAL_Y_MIN - 0.5, GOAL_Y_MAX + 0.5])
def test_ball_just_outside_the_goal_line_bounces(y):
    ball, events = ball_after_one_tick((2.0, y), (-40.0, 0.0))
    assert not events
    assert ball.velocity.x > 0


def test_ball_never_leaves_the_field():
    s, events = run(state(ball=(50.0, 10.0), velocity=(37.0, -53.0)), 400)
    assert not events
    assert BALL_RADIUS <= s.ball.position.x <= FIELD_LENGTH - BALL_RADIUS
    assert BALL_RADIUS <= s.ball.position.y <= FIELD_WIDTH - BALL_RADIUS


def test_free_ball_slows_down_and_stops():
    s, _ = run(state(ball=(50.0, 30.0), velocity=(0.0, 10.0)), 400)
    assert s.ball.velocity == ZERO


def test_friction_is_applied_every_tick():
    ball, _ = ball_after_one_tick((50.0, 30.0), (10.0, 0.0))
    assert ball.velocity.x == pytest.approx(10.0 * BALL_FRICTION_PER_TICK)


def test_ball_crossing_just_outside_the_post_bounces_back_in():
    # Cruza la línea afuera del palo pero termina a la altura del arco.
    ball, events = ball_after_one_tick((1.0, GOAL_Y_MIN - 1.0), (-40.0, 20.0))
    assert not events
    assert ball.velocity.x > 0
    assert ball.position.x >= BALL_RADIUS
