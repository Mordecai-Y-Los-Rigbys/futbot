"""Constraints del modelo `substitutions` contra Postgres (integration).

Las reglas que miran otras tablas las hace cumplir un trigger de Postgres,
así que no se pueden probar con el SQLite de los unit tests.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.match import MatchStatus
from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.player import Player
from app.models.substitution import MAX_SUBSTITUTIONS_PER_TEAM, Substitution
from app.models.team_member import MemberRole, TeamMember

pytestmark = pytest.mark.integration

ROLES = [MemberRole.forward, MemberRole.midfield, MemberRole.defense] + [MemberRole.substitute] * 3


def add_team(db, user_id, behavior, **owner):
    """Crea 6 jugadores y su equipo en `owner` (league_id=... o match_id=...)."""
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
    members = [
        TeamMember(user_id=user_id, player_id=p.id, behavior_id=behavior.id, role=role, **owner)
        for p, role in zip(players, ROLES)
    ]
    db.add_all(members)
    db.commit()
    return members


def add_league(db, name="L"):
    league = League(
        name=name,
        creator_id=1,
        status=LeagueStatus.started,
        min_participants=3,
        max_participants=8,
        match_duration=2,
        private=False,
    )
    db.add(league)
    db.flush()
    return league


@pytest.fixture()
def league_match(db_session, make_user, make_behaviors):
    """Partido de liga `started` entre 1 y 2, con sus equipos de liga."""
    make_user(1), make_user(2)
    league = add_league(db_session)
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
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(match)
    db_session.commit()
    return match, teams


@pytest.fixture()
def friendly_match(db_session, make_user, make_behaviors):
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2, status=MatchStatus.started)
    db_session.add(match)
    db_session.commit()
    teams = {
        uid: add_team(db_session, uid, make_behaviors(uid, ["fb"], code="pass")[0], match_id=match.id)
        for uid in (1, 2)
    }
    return match, teams


def substitute(db, match, team, out_idx=0, in_idx=3):
    """Inserta un cambio: sale team[out_idx] y entra team[in_idx]."""
    sub = Substitution(
        match_id=match.id, member_in_id=team[in_idx].id, member_out_id=team[out_idx].id
    )
    db.add(sub)
    db.commit()
    return sub


def assert_rejected(db, match, member_in, member_out):
    db.add(Substitution(match_id=match.id, member_in_id=member_in.id, member_out_id=member_out.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- caso válido ---------------------------------------------------------------


def test_valid_substitution_in_league_match(db_session, league_match):
    match, teams = league_match
    sub = substitute(db_session, match, teams[1])

    assert sub.id is not None
    assert sub.match_id == match.id
    assert sub.member_in_id == teams[1][3].id
    assert sub.member_out_id == teams[1][0].id


def test_valid_substitution_in_friendly(db_session, friendly_match):
    match, teams = friendly_match
    substitute(db_session, match, teams[2])

    assert db_session.scalars(select(Substitution)).one().match_id == match.id


# --- el partido debe estar en juego ----------------------------------------------


@pytest.mark.parametrize("status", [MatchStatus.scheduled, MatchStatus.cancelled])
def test_match_not_started_is_rejected(db_session, league_match, status):
    match, teams = league_match
    match.status = status
    db_session.commit()

    assert_rejected(db_session, match, teams[1][3], teams[1][0])


def test_finished_match_is_rejected(db_session, league_match):
    match, teams = league_match
    match.status = MatchStatus.finished
    match.score_1, match.score_2 = 1, 0
    db_session.commit()

    assert_rejected(db_session, match, teams[1][3], teams[1][0])


# --- mismo equipo ----------------------------------------------------------------


def test_members_of_different_teams_are_rejected(db_session, league_match):
    match, teams = league_match

    assert_rejected(db_session, match, teams[2][3], teams[1][0])


def test_same_member_in_and_out_is_rejected(db_session, league_match):
    match, teams = league_match

    assert_rejected(db_session, match, teams[1][0], teams[1][0])


# --- el equipo debe ser del partido ----------------------------------------------


def test_team_of_another_league_is_rejected(db_session, league_match, make_behaviors):
    match, _ = league_match
    other = add_league(db_session, name="Otra")
    db_session.add(LeagueParticipant(league_id=other.id, user_id=1))
    db_session.flush()
    foreign = add_team(db_session, 1, make_behaviors(1, ["x"], code="pass")[0], league_id=other.id)

    assert_rejected(db_session, match, foreign[3], foreign[0])


def test_team_of_another_friendly_is_rejected(db_session, friendly_match, make_behaviors):
    match, _ = friendly_match
    other = Match(user_1_id=1, user_2_id=2, status=MatchStatus.started)
    db_session.add(other)
    db_session.commit()
    foreign = add_team(db_session, 1, make_behaviors(1, ["y"], code="pass")[0], match_id=other.id)

    assert_rejected(db_session, match, foreign[3], foreign[0])


def test_team_of_a_user_not_in_the_match_is_rejected(
    db_session, league_match, make_user, make_behaviors
):
    match, _ = league_match
    make_user(3)
    db_session.add(LeagueParticipant(league_id=match.league_id, user_id=3))
    db_session.flush()
    outsider = add_team(
        db_session, 3, make_behaviors(3, ["z"], code="pass")[0], league_id=match.league_id
    )

    assert_rejected(db_session, match, outsider[3], outsider[0])


# --- hasta tres cambios por equipo -----------------------------------------------


def test_up_to_three_substitutions_per_team_and_fourth_is_rejected(db_session, league_match):
    match, teams = league_match
    for i in range(MAX_SUBSTITUTIONS_PER_TEAM):
        substitute(db_session, match, teams[1], out_idx=i, in_idx=3 + i)

    assert_rejected(db_session, match, teams[1][3], teams[1][0])


def test_limit_is_per_team_not_per_match(db_session, league_match):
    match, teams = league_match
    for uid in (1, 2):
        for i in range(MAX_SUBSTITUTIONS_PER_TEAM):
            substitute(db_session, match, teams[uid], out_idx=i, in_idx=3 + i)

    assert len(db_session.scalars(select(Substitution)).all()) == 2 * MAX_SUBSTITUTIONS_PER_TEAM


def test_limit_is_per_match(db_session, league_match):
    match, teams = league_match
    other = Match(
        league_id=match.league_id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
    )
    db_session.add(other)
    db_session.commit()
    for i in range(MAX_SUBSTITUTIONS_PER_TEAM):
        substitute(db_session, match, teams[1], out_idx=i, in_idx=3 + i)

    substitute(db_session, other, teams[1])


# --- cascade ---------------------------------------------------------------------


def test_substitutions_are_deleted_with_the_match(db_session, friendly_match):
    match, teams = friendly_match
    substitute(db_session, match, teams[1])

    db_session.delete(match)
    db_session.commit()

    assert db_session.scalars(select(Substitution)).all() == []