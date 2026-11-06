"""Ejecución de la sustitución en MatchSession (sin I/O)."""

import pytest

from app.domain.team_member import MemberRole
from app.simulation import constants as C
from app.simulation.actions import GoTo
from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.match_rules import Event, Phase, build_session
from app.simulation.physics import PlayerSetup
from app.simulation.run import default_team as make_team
from app.simulation.state import Stats, Team

SEED = 1
STATS = Stats(power=10, agility=20, control=30, strength=40, speed=50)
SUBSTITUTE_BEHAVIOR = compile_behavior("go_to(11, 22)")
SUBSTITUTE_MOVE = GoTo(11, 22)


def make():
    """8 s de juego en 4 períodos de 2 s: pausas y cuentas de 1 s."""
    return build_session(make_team(), make_team(first_id=10), 8, SEED, 1, 4, 1)


def substitute(session, team=Team.HOME, role=MemberRole.forward, player_id=99):
    session.substitute(team, role, PlayerSetup(player_id, role, STATS), SUBSTITUTE_BEHAVIOR)


def to_next_pause(session):
    """Avanza hasta justo antes del primer tick de la próxima pausa."""
    ticks = []
    while not session.next_tick_starts_pause:
        ticks.append(session.advance())
    return ticks


def first_play_tick(session, period):
    while True:
        tick = session.advance()
        if tick.phase is Phase.PLAYING and tick.period == period:
            return tick


# --- cuándo se dispara ---------------------------------------------------------


def test_the_trigger_is_true_only_right_before_the_first_tick_of_each_pause():
    session = make()
    starts = 0
    while not session.finished:
        if session.next_tick_starts_pause:
            starts += 1
            assert session.advance().event is Event.PAUSE
        else:
            session.advance()
    assert starts == 3  # una por pausa, no una por tick de pausa


def test_the_trigger_is_false_during_the_rest_of_the_pause():
    session = make()
    to_next_pause(session)
    session.advance()  # primer tick de la pausa
    assert session.next_tick_starts_pause is False


# --- el suplente entra ---------------------------------------------------------


def test_the_tick_shows_the_substitute_in_the_position_of_the_starter():
    session = make()
    last_before = to_next_pause(session)[-1]
    position = last_before.state.player((Team.HOME, 3)).position

    substitute(session)
    tick = session.advance()

    assert tick.phase is Phase.PAUSED
    entering = tick.state.player((Team.HOME, 3))
    assert entering.player_id == 99
    assert entering.role is MemberRole.forward
    assert entering.position == position


def test_the_substitute_does_not_inherit_the_movement_or_cooldowns_of_the_starter():
    session = make()
    to_next_pause(session)
    starter = session._state.player((Team.HOME, 3))
    starter.move = GoTo(1, 1)
    starter.next_kick_tick = 500
    starter.regain_blocked_until = 600

    substitute(session)
    entering = session.advance().state.player((Team.HOME, 3))

    assert entering.move is None
    assert entering.next_kick_tick == C.NO_KICK_COOLDOWN
    assert entering.regain_blocked_until == C.NOT_REGAIN_BLOCKED


def test_the_substitute_uses_its_own_stats():
    session = make()
    to_next_pause(session)
    substitute(session)
    assert session.advance().state.player((Team.HOME, 3)).stats == STATS


def test_ticks_already_emitted_do_not_change():
    session = make()
    last_before = to_next_pause(session)[-1]
    original_id = last_before.state.player((Team.HOME, 3)).player_id

    substitute(session)
    session.advance()

    assert last_before.state.player((Team.HOME, 3)).player_id == original_id


def test_only_the_substituted_slot_changes():
    session = make()
    to_next_pause(session)
    substitute(session, team=Team.HOME, role=MemberRole.midfield)
    state = session.advance().state

    assert state.player((Team.HOME, 2)).player_id == 99
    assert state.player((Team.HOME, 1)).player_id == 1
    assert state.player((Team.HOME, 3)).player_id == 3
    assert sorted(p.player_id for p in state.players if p.team is Team.AWAY) == [11, 12, 13]


def test_the_away_team_can_substitute_too():
    session = make()
    to_next_pause(session)
    substitute(session, team=Team.AWAY, role=MemberRole.defense, player_id=77)
    state = session.advance().state

    assert state.player((Team.AWAY, 1)).player_id == 77
    assert state.player((Team.HOME, 1)).player_id == 1


# --- juega con su comportamiento ----------------------------------------------


def test_the_substitute_plays_with_its_behavior_from_the_first_play_tick_after_the_pause():
    session = make()
    to_next_pause(session)
    substitute(session)

    tick = first_play_tick(session, period=2)

    assert tick.state.player((Team.HOME, 3)).move == SUBSTITUTE_MOVE


def test_the_rest_of_the_team_keeps_its_behaviors():
    session = make()
    to_next_pause(session)
    substitute(session)

    tick = first_play_tick(session, period=2)

    assert tick.state.player((Team.HOME, 2)).move != SUBSTITUTE_MOVE
    assert tick.state.player((Team.HOME, 1)).move != SUBSTITUTE_MOVE


# --- siempre 3 titulares -------------------------------------------------------


def test_there_are_always_three_starters_per_team_after_three_substitutions():
    session = make()
    roles = [MemberRole.forward, MemberRole.midfield, MemberRole.defense]
    for index, role in enumerate(roles):
        to_next_pause(session)
        substitute(session, role=role, player_id=100 + index)
        state = session.advance().state
        for team in (Team.HOME, Team.AWAY):
            assert sorted(p.number for p in state.players if p.team is team) == [1, 2, 3]

    assert {p.player_id for p in state.players if p.team is Team.HOME} == {100, 101, 102}


def test_a_substitute_cannot_take_the_place_of_a_substitute():
    session = make()
    to_next_pause(session)
    with pytest.raises(ValueError):
        session.substitute(
            Team.HOME,
            MemberRole.substitute,
            PlayerSetup(99, MemberRole.substitute, STATS),
            SUBSTITUTE_BEHAVIOR,
        )
