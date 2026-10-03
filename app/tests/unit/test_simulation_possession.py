import pytest

from app.simulation.constants import POSSESSION_PROTECTION_TICKS
from app.simulation.geometry import ZERO
from app.simulation.physics import reach, step
from app.tests.unit.simulation_helpers import AWAY, HOME, player, run, state

H, A = (HOME, 1), (AWAY, 1)



# --- posesión -----------------------------------------------------------------------


def test_player_within_reach_gets_the_ball():
    assert reach(60) == pytest.approx(4.2)
    s = step(state(player(HOME, 1, x=50.0), ball=(54.0, 30.0))).state
    assert s.ball.owner == H


def test_player_out_of_reach_does_not():
    s = step(state(player(HOME, 1, x=50.0), ball=(54.5, 30.0))).state
    assert s.ball.owner is None


def test_owned_ball_goes_in_front_of_the_player():
    s = step(state(player(HOME, 1, x=50.0), ball=(53.0, 30.0))).state
    s = step(s).state
    assert s.ball.position.x == pytest.approx(53.0)
    assert s.ball.velocity == ZERO


def test_stronger_player_wins_a_disputed_ball():
    s = state(
        player(HOME, 1, x=50.0, strength=40),
        player(AWAY, 1, x=56.0, strength=80),
        ball=(53.0, 30.0),
    )
    assert step(s).state.ball.owner == A


def test_with_equal_strength_the_closest_wins():
    s = state(
        player(HOME, 1, x=50.0),
        player(AWAY, 1, x=56.5),
        ball=(53.0, 30.0),
    )
    assert step(s).state.ball.owner == H


def disputed_exact_tie(seed):
    return state(player(HOME, 1, x=50.0), player(AWAY, 1, x=56.0), ball=(53.0, 30.0), seed=seed)


def test_exact_tie_is_reproducible_with_the_same_seed():
    winners = {step(disputed_exact_tie(7)).state.ball.owner for _ in range(5)}
    assert len(winners) == 1


def test_exact_tie_can_go_either_way_depending_on_the_seed():
    winners = {step(disputed_exact_tie(seed)).state.ball.owner for seed in range(30)}
    assert winners == {H, A}


def test_protection_prevents_stealing_the_ball():
    s = state(
        player(HOME, 1, x=50.0, strength=40),
        player(AWAY, 1, x=56.0, strength=80),
        ball=(53.0, 30.0),
        owner=H,
    )
    s.ball.protected_until = POSSESSION_PROTECTION_TICKS

    s, _ = run(s, POSSESSION_PROTECTION_TICKS)
    assert s.ball.owner == H  # protegido

    s = step(s).state
    assert s.ball.owner == A  # vencida la protección, gana el más fuerte


def test_winning_the_ball_grants_protection():
    s = step(state(player(HOME, 1, x=50.0), ball=(53.0, 30.0))).state
    assert s.ball.protected_until == s.tick + POSSESSION_PROTECTION_TICKS
