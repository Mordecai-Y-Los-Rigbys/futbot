import pytest

from app.simulation.actions import MoveInDirection, PlayerActions
from app.simulation.constants import PLAYER_RADIUS, TICKS_PER_SECOND
from app.simulation.physics import player_speed, step
from app.tests.unit.simulation_helpers import AWAY, HOME, player, run, state

A, B = (HOME, 1), (AWAY, 1)


def overlapping(strength_a, strength_b):
    # Separados 3 u: se superponen 1 u (el mínimo es 2 radios = 4 u).
    return state(
        player(HOME, 1, x=50.0, strength=strength_a),
        player(AWAY, 1, x=53.0, strength=strength_b),
    )


def test_weaker_player_absorbs_most_of_the_displacement():
    s = step(overlapping(80, 20)).state
    assert s.player(A).position.x == pytest.approx(50.0 - 0.2)  # absorbe el 20 %
    assert s.player(B).position.x == pytest.approx(53.0 + 0.8)  # absorbe el 80 %


def test_equal_strength_split_the_displacement():
    s = step(overlapping(60, 60)).state
    assert s.player(A).position.x == pytest.approx(49.5)
    assert s.player(B).position.x == pytest.approx(53.5)


def test_players_never_end_overlapped():
    s = step(overlapping(60, 60)).state
    distance = (s.player(B).position - s.player(A).position).length()
    assert distance >= 2 * PLAYER_RADIUS - 1e-9


def test_players_on_the_same_spot_are_separated():
    s = step(state(player(HOME, 1, x=50.0), player(AWAY, 1, x=50.0))).state
    distance = (s.player(B).position - s.player(A).position).length()
    assert distance == pytest.approx(2 * PLAYER_RADIUS)


def test_pushing_is_slower_than_running_free():
    s = state(player(HOME, 1, x=50.0), player(AWAY, 1, x=54.0))
    actions = {A: PlayerActions(move=MoveInDirection(1, 0))}
    s, _ = run(s, TICKS_PER_SECOND, actions)

    advanced = s.player(A).position.x - 50.0
    assert advanced > 0  # empuja
    assert advanced < player_speed(60)  # pero más lento que corriendo libre
    assert s.player(B).position.x > 54.0  # el otro cede terreno


def test_separation_respects_the_borders():
    s = step(state(player(HOME, 1, x=2.0), player(AWAY, 1, x=3.0))).state
    assert s.player(A).position.x >= PLAYER_RADIUS
    assert s.player(B).position.x >= PLAYER_RADIUS


def test_three_players_overlapping_are_all_separated():
    s = step(
        state(
            player(HOME, 1, x=50.0),
            player(HOME, 2, x=52.0),
            player(AWAY, 1, x=54.0),
        )
    ).state
    positions = [p.position for p in s.players]
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            assert (b - a).length() >= 2 * PLAYER_RADIUS - 1e-3  # tolerancia numérica

def test_separating_a_pair_can_create_a_new_overlap_that_is_also_resolved():
    # Orden de los pares: (AWAY 1, AWAY 2), (AWAY 1, HOME 1), (AWAY 2, HOME 1).
    s = step(
        state(
            player(AWAY, 1, x=50.0),
            player(AWAY, 2, x=46.0),
            player(HOME, 1, x=53.0),
        )
    ).state
    positions = [p.position for p in s.players]
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            assert (b - a).length() >= 2 * PLAYER_RADIUS - 1e-3