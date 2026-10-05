import pytest

from app.simulation.actions import Kick, KickTo, PlayerActions
from app.simulation.constants import (
    BALL_CARRY_SPEED,
    KICKER_REGAIN_BLOCK_TICKS,
    POSSESSION_PROTECTION_TICKS,
    TICKS_PER_SECOND,
)
from app.simulation.geometry import ZERO
from app.simulation.physics import kick_cooldown_ticks, max_kick_speed, reach, step
from app.tests.unit.simulation_helpers import AWAY, HOME, player, run, state

H, A = (HOME, 1), (AWAY, 1)


def kick(key, action):
    return {key: PlayerActions(kick=action)}


# --- posesión -----------------------------------------------------------------


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


def test_won_ball_moves_gradually_to_the_front_of_the_player():
    # Gana una pelota que está al costado: no aparece de golpe adelante, se acerca.
    s = step(state(player(HOME, 1, x=50.0), ball=(50.0, 34.0))).state
    assert s.ball.owner == H

    before = s.ball.position
    s = step(s).state
    moved = (s.ball.position - before).length()
    assert moved == pytest.approx(BALL_CARRY_SPEED / TICKS_PER_SECOND)

    s, _ = run(s, 3)
    assert s.ball.position.x == pytest.approx(53.0)
    assert s.ball.position.y == pytest.approx(30.0)


# --- patadas ------------------------------------------------------------------


def owned_ball(**stat_values):
    """Local en (50, 30) con la pelota adelante (53, 30)."""
    return state(player(HOME, 1, x=50.0, **stat_values), ball=(53.0, 30.0), owner=H)


@pytest.mark.parametrize("force", [100, 40])
def test_kick_speed_follows_the_formula(force):
    assert max_kick_speed(60) == pytest.approx(44.0)
    s = step(owned_ball(power=60), kick(H, Kick(force=force))).state
    assert s.ball.owner is None
    assert s.ball.velocity.x == pytest.approx(force / 100 * 44.0)
    assert s.ball.velocity.y == pytest.approx(0.0)


@pytest.mark.parametrize("force, expected", [(0, 1), (-5, 1), (250, 100)])
def test_kick_force_is_clamped(force, expected):
    s = step(owned_ball(power=60), kick(H, Kick(force=force))).state
    assert s.ball.velocity.x == pytest.approx(expected / 100 * 44.0)


def test_kick_without_the_ball_does_nothing():
    s = step(state(player(HOME, 1, x=20.0), ball=(80.0, 30.0)), kick(H, Kick())).state
    assert s.ball.velocity == ZERO


def test_kick_to_a_target_in_front():
    s = step(owned_ball(), kick(H, KickTo(100.0, 30.0))).state
    assert s.ball.velocity.y == pytest.approx(0.0)
    assert s.ball.velocity.x > 0


def test_kick_to_a_target_behind_goes_to_the_closest_side():
    # Mira hacia +x y el destino queda atrás y abajo: patea a 90°, hacia abajo.
    s = step(owned_ball(), kick(H, KickTo(10.0, 20.0))).state
    assert s.ball.velocity.x == pytest.approx(0.0)
    assert s.ball.velocity.y < 0


def test_cooldown_blocks_the_kick():
    assert kick_cooldown_ticks(60) == 15
    s = owned_ball(agility=60)
    s.players[0].next_kick_tick = 5

    s = step(s, kick(H, Kick())).state  # tick 1: en cooldown
    assert s.ball.owner == H

    s, _ = run(s, 3)  # ticks 2 a 4
    s = step(s, kick(H, Kick())).state  # tick 5: ya puede
    assert s.ball.owner is None


def test_kicking_starts_the_cooldown():
    s = step(owned_ball(agility=60), kick(H, Kick())).state
    assert s.player(H).next_kick_tick == s.tick + kick_cooldown_ticks(60)


def test_kicker_cannot_regain_the_ball_right_away():
    # Patada mínima: la pelota casi no se aleja y queda al alcance.
    s = step(owned_ball(), kick(H, Kick(force=1))).state
    assert s.ball.owner is None

    s, _ = run(s, KICKER_REGAIN_BLOCK_TICKS)
    assert s.ball.owner is None

    s = step(s).state
    assert s.ball.owner == H


def test_another_player_can_take_a_kicked_ball():
    s = state(
        player(HOME, 1, x=50.0),
        player(AWAY, 1, x=60.0),
        ball=(53.0, 30.0),
        owner=H,
    )
    s = step(s, kick(H, Kick(force=20))).state
    s, _ = run(s, 10)
    assert s.ball.owner == A
