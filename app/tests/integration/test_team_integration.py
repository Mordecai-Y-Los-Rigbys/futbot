"""Queries de equipos y partidos contra la base real (integration).

Cubre lo que el unit de MatchSetupService no puede: el SQL de los repositories
y los constraints de team_members.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository

pytestmark = pytest.mark.integration

ROLES = [MemberRole.forward, MemberRole.midfield, MemberRole.defense] + [MemberRole.substitute] * 3


def make_players(db, user_id):
    players = [
        Player(
            user_id=user_id,
            name=f"p{user_id}{i}",
            power=60,
            agility=60,
            control=60,
            strength=60,
            speed=60,
        )
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
    league = League(
        name="L",
        creator_id=1,
        status=LeagueStatus.started,
        min_participants=3,
        max_participants=8,
        match_duration=2,
        private=False,
    )
    db_session.add(league)
    db_session.flush()
    teams = {}
    for uid in (1, 2):
        db_session.add(LeagueParticipant(league_id=league.id, user_id=uid))
        db_session.flush()
        behavior = make_behaviors(uid, ["b"], code="pass")[0]
        teams[uid] = add_team(db_session, uid, behavior, league_id=league.id)
    match = Match(
        league_id=league.id,
        user_1_id=1,
        user_2_id=2,
        scheduled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(match)
    db_session.commit()
    return match, teams


# --- SqlAlchemyTeamRepository.get_starters ------------------------------------


def test_league_match_returns_only_the_three_league_starters(db_session, league_match):
    match, _ = league_match
    rows = SqlAlchemyTeamRepository(db_session).get_starters(match.id, match.league_id, 1)

    assert len(rows) == 3
    assert {r.role for r in rows} == {"forward", "midfield", "defense"}
    assert all(r.behavior_code == "pass" for r in rows)


def test_each_user_gets_only_their_own_team(db_session, league_match):
    match, teams = league_match
    repo = SqlAlchemyTeamRepository(db_session)
    ids_1 = {r.player_id for r in repo.get_starters(match.id, match.league_id, 1)}
    ids_2 = {r.player_id for r in repo.get_starters(match.id, match.league_id, 2)}

    assert ids_1.isdisjoint(ids_2)
    assert ids_1 <= {m.player_id for m in teams[1]}


def test_friendly_returns_the_match_team(db_session, make_user, make_behaviors):
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2)
    db_session.add(match)
    db_session.commit()
    for uid in (1, 2):
        add_team(db_session, uid, make_behaviors(uid, ["fb"], code="pass")[0], match_id=match.id)

    rows = SqlAlchemyTeamRepository(db_session).get_starters(match.id, None, 1)
    assert len(rows) == 3


def test_friendly_without_members_returns_empty(db_session, make_user):
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2)
    db_session.add(match)
    db_session.commit()

    assert SqlAlchemyTeamRepository(db_session).get_starters(match.id, None, 1) == []


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

    rows = SqlAlchemyTeamRepository(db_session).get_starters(match.id, match.league_id, 1)
    new_forward = next(r for r in rows if r.role == "forward")
    # entró el suplente con su propio behavior; el que salió ya no juega
    assert new_forward.player_id == substitute.player_id
    assert new_forward.behavior_code == "pass"
    assert forward.player_id not in {r.player_id for r in rows}


# --- SqlAlchemyMatchRepository.get_setup_data ---------------------------------


def test_setup_data_has_both_club_names(db_session, league_match):
    match, _ = league_match
    data = SqlAlchemyMatchRepository(db_session).get_setup_data(match.id)

    assert (data.club_1_name, data.club_2_name) == ("club1", "club2")
    assert (data.user_1_id, data.user_2_id, data.league_id) == (1, 2, match.league_id)


def test_setup_data_of_a_match_without_rival_has_no_second_club(db_session, make_user):
    make_user(1)
    match = Match(user_1_id=1)
    db_session.add(match)
    db_session.commit()

    data = SqlAlchemyMatchRepository(db_session).get_setup_data(match.id)
    assert data.user_2_id is None and data.club_2_name is None


def test_setup_data_of_an_unknown_match_is_none(db_session):
    assert SqlAlchemyMatchRepository(db_session).get_setup_data(999) is None


# --- SqlAlchemyLeagueRepository.get_match_duration_minutes --------------------


def test_league_duration_in_minutes(db_session, league_match):
    match, _ = league_match
    assert SqlAlchemyLeagueRepository(db_session).get_match_duration_minutes(match.league_id) == 2


def test_duration_of_an_unknown_league_is_none(db_session):
    assert SqlAlchemyLeagueRepository(db_session).get_match_duration_minutes(999) is None


# --- Constraint de team_members -----------------------------------------------


@pytest.mark.parametrize("owner", [{}, {"league_id": 1, "match_id": 1}])
def test_a_member_belongs_to_exactly_one_of_league_or_match(
    db_session, make_user, make_behaviors, owner
):
    make_user(1)
    player = make_players(db_session, 1)[0]
    behavior = make_behaviors(1, ["b"], code="pass")[0]
    db_session.add(
        TeamMember(
            user_id=1,
            player_id=player.id,
            behavior_id=behavior.id,
            role=MemberRole.forward,
            **owner,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
