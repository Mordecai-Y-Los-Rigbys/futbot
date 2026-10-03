"""Carga de equipos desde team_members (SQLite en memoria, sin marker integration)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.services.match_setup import load_match_setup
from app.simulation.match_rules import FRIENDLY_MATCH_DURATION
from app.simulation.state import Role

ROLES = [MemberRole.forward, MemberRole.midfield, MemberRole.defense] + [MemberRole.substitute] * 3


def make_players(db, user_id):
    players = [
        Player(user_id=user_id, name=f"p{user_id}{i}", power=60, agility=60,
               control=60, strength=60, speed=60)
        for i in range(6)
    ]
    db.add_all(players)
    db.commit()
    return players


def add_team(db, user_id, behavior, **owner):
    """Crea 6 jugadores y su equipo en `owner` (league_id=... o match_id=...)."""
    members = [
        TeamMember(user_id=user_id, player_id=p.id, behavior_id=behavior.id, role=role, **owner)
        for p, role in zip(make_players(db, user_id), ROLES)
    ]
    db.add_all(members)
    db.commit()
    return members


@pytest.fixture()
def league_match(db_session, make_user, make_behaviors):
    make_user(1), make_user(2)
    league = League(name="L", creator_id=1, status=LeagueStatus.started, min_participants=3,
                    max_participants=8, match_duration=2, private=False)
    db_session.add(league)
    db_session.flush()
    teams = {}
    for uid in (1, 2):
        db_session.add(LeagueParticipant(league_id=league.id, user_id=uid))
        db_session.flush()
        behavior = make_behaviors(uid, ["b"], code="pass")[0]
        teams[uid] = add_team(db_session, uid, behavior, league_id=league.id)
    match = Match(league_id=league.id, user_1_id=1, user_2_id=2,
                  scheduled_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    db_session.add(match)
    db_session.commit()
    return match, teams


def test_league_match_loads_the_league_teams(db_session, league_match):
    match, _ = league_match
    setup = load_match_setup(db_session, match.id)
    assert setup.duration_seconds == 120
    assert (setup.club_1_name, setup.club_2_name) == ("club1", "club2")
    for team in (setup.team_1, setup.team_2):
        assert {p.role for p in team.players} == set(Role)
        assert set(team.behaviors) == set(Role)


def test_reassigned_behavior_and_substitution_persist_to_the_next_match(
    db_session, league_match, make_behaviors
):
    match, teams = league_match
    new_behavior = make_behaviors(1, ["nuevo"], code="go_to(1, 2)")[0]
    forward = next(m for m in teams[1] if m.role is MemberRole.forward)
    substitute = next(m for m in teams[1] if m.role is MemberRole.substitute)

    forward.behavior_id = new_behavior.id  # reasignar behavior
    forward.role, substitute.role = MemberRole.substitute, MemberRole.forward  # sustitución
    db_session.commit()

    team_1 = load_match_setup(db_session, match.id).team_1
    assert next(p for p in team_1.players if p.role is Role.FORWARD).player_id == substitute.player_id
    # el sustituto conserva su behavior; el que salió ya no juega
    assert "go_to" not in team_1.behaviors[Role.FORWARD].code.co_names


def test_friendly_uses_the_match_team_and_fixed_duration(db_session, make_user, make_behaviors):
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2)
    db_session.add(match)
    db_session.commit()
    for uid in (1, 2):
        add_team(db_session, uid, make_behaviors(uid, ["fb"], code="pass")[0], match_id=match.id)

    setup = load_match_setup(db_session, match.id)
    assert setup.duration_seconds == FRIENDLY_MATCH_DURATION * 60


def test_friendly_without_members_is_an_error(db_session, make_user):
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2)
    db_session.add(match)
    db_session.commit()
    with pytest.raises(ValueError):
        load_match_setup(db_session, match.id)


@pytest.mark.parametrize("owner", [{}, {"league_id": 1, "match_id": 1}])
def test_a_member_belongs_to_exactly_one_of_league_or_match(db_session, make_user, make_behaviors, owner):
    make_user(1)
    player = make_players(db_session, 1)[0]
    behavior = make_behaviors(1, ["b"], code="pass")[0]
    db_session.add(TeamMember(user_id=1, player_id=player.id, behavior_id=behavior.id,
                              role=MemberRole.forward, **owner))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()