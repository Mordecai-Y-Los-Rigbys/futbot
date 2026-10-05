import ast
import copy
from pathlib import Path

import pytest

import app.simulation as simulation_pkg
from app.simulation.actions import GoTo, Kick, MoveInDirection, PlayerActions
from app.simulation.constants import (
    FIELD_LENGTH, 
    FIELD_WIDTH, 
    NO_KICK_COOLDOWN, 
    NOT_REGAIN_BLOCKED, 
    STARTER_ROLES
)
from app.simulation.geometry import Vec
from app.simulation.physics import (
    PlayerSetup,
    create_initial_state,
    reset_positions,
    step,
)
from app.domain.team_member import MemberRole
from app.tests.unit.simulation_helpers import AWAY, HOME, stats


def team(first_id):
    return [PlayerSetup(player_id=first_id + i, role=r, stats=stats()) for i, r in enumerate(STARTER_ROLES)]


def initial(seed=1):
    return create_initial_state(team(1), team(11), seed=seed)


# --- estado inicial ---------------------------------------------------------------


@pytest.mark.parametrize(
    "key, expected",
    [
        ((HOME, 1), (12.0, 30.0)),
        ((HOME, 2), (26.0, 30.0)),
        ((HOME, 3), (40.0, 30.0)),
        ((AWAY, 3), (60.0, 30.0)),  # el visitante queda rotado 180°
        ((AWAY, 1), (88.0, 30.0)),
    ],
)
def test_initial_positions_by_role(key, expected):
    assert initial().player(key).position == Vec(*expected)


def test_ball_starts_free_in_the_center():
    ball = initial().ball
    assert ball.position == Vec(FIELD_LENGTH / 2, FIELD_WIDTH / 2)
    assert ball.owner is None


def test_both_forwards_are_at_the_same_distance_from_the_ball():
    s = initial()
    home = (s.player((HOME, 3)).position - s.ball.position).length()
    away = (s.player((AWAY, 3)).position - s.ball.position).length()
    assert home == pytest.approx(away)


def test_a_team_needs_one_player_per_role():
    bad = [PlayerSetup(1, MemberRole.forward, stats()) for _ in range(3)]
    with pytest.raises(ValueError):
        create_initial_state(bad, team(11), seed=1)


def test_reset_positions_puts_everyone_back_and_keeps_the_tick():
    s = initial()
    actions = {(HOME, 3): PlayerActions(move=GoTo(80.0, 10.0))}
    for _ in range(30):
        s = step(s, actions).state

    reset = reset_positions(s)
    assert reset.tick == s.tick
    assert reset.player((HOME, 3)).position == Vec(40.0, 30.0)
    assert reset.player((HOME, 3)).move is None
    assert reset.ball.owner is None

def test_reset_positions_clears_the_cooldowns():
    s = initial()
    p = s.player((HOME, 3))
    p.next_kick_tick = 500
    p.regain_blocked_until = 500

    reset = reset_positions(s)
    assert reset.player((HOME, 3)).next_kick_tick == NO_KICK_COOLDOWN
    assert reset.player((HOME, 3)).regain_blocked_until == NOT_REGAIN_BLOCKED

# --- determinismo y pureza ---------------------------------------------------------


def busy_actions():
    return {
        (HOME, 3): PlayerActions(move=GoTo(50.0, 30.0), kick=Kick()),
        (AWAY, 3): PlayerActions(move=GoTo(50.0, 30.0), kick=Kick()),
        (HOME, 2): PlayerActions(move=MoveInDirection(1, 1)),
    }


def play(seed, ticks=200):
    s = initial(seed)
    events = []
    for _ in range(ticks):
        result = step(s, busy_actions())
        s, events = result.state, events + list(result.events)
    return s, events


def test_same_input_gives_the_same_result():
    assert play(seed=3) == play(seed=3)


def test_step_does_not_modify_the_given_state():
    s = initial()
    before = copy.deepcopy(s)
    step(s, busy_actions())
    assert s == before


# --- constantes ------------------------------------------------------------------------


@pytest.mark.parametrize("module", ["physics.py", "geometry.py"])
def test_no_tunable_numbers_outside_constants(module):
    """Todos los parámetros del motor están en constants.py."""
    source = (Path(simulation_pkg.__file__).parent / module).read_text(encoding="utf-8")
    allowed = {0, 1, 2}
    found = [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
        and node.value not in allowed
    ]
    assert found == []
