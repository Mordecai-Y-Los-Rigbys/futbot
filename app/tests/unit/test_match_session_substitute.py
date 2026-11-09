import pytest

from app.domain.team_member import MemberRole
from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.match_rules import Event, build_session
from app.simulation.physics import PlayerSetup
from app.simulation.run import default_team
from app.simulation.state import Stats, Team

STATS = Stats(power=70, agility=50, control=60, strength=60, speed=60)


def session():
    # 4 períodos, 2 s de juego, cuentas y pausas de 1 s.
    return build_session(default_team(0), default_team(10), 2, 42, 1, 4, 1)


def first_pause_tick(s):
    while True:
        result = s.advance()
        if result.event is Event.PAUSE:
            return result


def incoming(player_id=99, role=MemberRole.forward):
    return PlayerSetup(player_id, role, STATS)


def test_substitute_takes_the_place_stats_and_behavior_of_the_starter():
    s = session()
    first_pause_tick(s)
    behavior = compile_behavior("pass")

    s.substitute(Team.HOME, 3, incoming(), behavior)

    forward = s.state.player((Team.HOME, 3))
    assert forward.player_id == 99 and forward.stats == STATS
    assert forward.role is MemberRole.forward
    assert {p.player_id for p in s.state.players} == {1, 2, 99, 11, 12, 13}
    assert s._behaviors[(Team.HOME, 3)] is behavior


def test_ticks_already_emitted_are_not_modified():
    s = session()
    tick = first_pause_tick(s)

    s.substitute(Team.HOME, 3, incoming(), compile_behavior("pass"))

    assert 3 in {p.player_id for p in tick.state.players}
    assert 99 not in {p.player_id for p in tick.state.players}


def test_the_match_goes_on_to_the_end_after_a_substitution():
    s = session()
    first_pause_tick(s)
    s.substitute(Team.AWAY, 13, incoming(98), compile_behavior("pass"))
    while not s.finished:
        last = s.advance()
    assert 98 in {p.player_id for p in last.state.players}


def test_substitute_rejects_a_player_that_is_not_on_the_field():
    with pytest.raises(ValueError):
        session().substitute(Team.HOME, 77, incoming(), compile_behavior("pass"))


def test_substitute_rejects_a_role_different_from_the_starter_s():
    with pytest.raises(ValueError):
        session().substitute(
            Team.HOME, 3, incoming(role=MemberRole.defense), compile_behavior("pass")
        )


def test_substitute_only_looks_in_the_given_team():
    with pytest.raises(ValueError):
        session().substitute(Team.AWAY, 3, incoming(), compile_behavior("pass"))  # el 3 es local


def test_periods_property():
    assert session().periods == 4
