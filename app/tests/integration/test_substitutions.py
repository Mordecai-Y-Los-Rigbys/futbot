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
from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository

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
        uid: add_team(
            db_session, uid, make_behaviors(uid, ["fb"], code="pass")[0], match_id=match.id
        )
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


def remaining_ids(db):
    db.expire_all()
    return {s.id for s in db.scalars(select(Substitution)).all()}


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


# --- delete_first_substitutions (fin de cada pausa) -------------------------------


def test_delete_first_substitution_of_each_team(db_session, league_match):
    match, teams = league_match
    subs = {
        uid: [substitute(db_session, match, teams[uid], out_idx=i, in_idx=3 + i) for i in range(2)]
        for uid in (1, 2)
    }
    # Los ids se guardan antes: después del delete esas instancias ya no existen.
    second_ids = {subs[1][1].id, subs[2][1].id}
    # test_delete_first_substitution_of_each_team
    repo = SqlAlchemySubstitutionRepository(db_session)

    assert repo.delete_first_per_team(match.id) == 2
    assert remaining_ids(db_session) == second_ids  # quedan los segundos

    assert repo.delete_first_per_team(match.id) == 2  # la pausa siguiente
    assert remaining_ids(db_session) == set()
    assert repo.delete_first_per_team(match.id) == 0  # sin cambios, no falla

def test_only_the_team_with_substitutions_loses_one(db_session, league_match):
    match, teams = league_match
    keep = [substitute(db_session, match, teams[2], out_idx=i, in_idx=3 + i) for i in range(2)]
    second_id = keep[1].id

    SqlAlchemySubstitutionRepository(db_session).delete_first_per_team(match.id)

    assert remaining_ids(db_session) == {second_id}


def test_first_means_lowest_id_not_insertion_of_another_team(db_session, league_match):
    match, teams = league_match
    first_1 = substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    first_2 = substitute(db_session, match, teams[2], out_idx=0, in_idx=3)
    second_1 = substitute(db_session, match, teams[1], out_idx=1, in_idx=4)
    survivors = {second_1.id}
    assert first_1.id < second_1.id and first_2.id > first_1.id

    SqlAlchemySubstitutionRepository(db_session).delete_first_per_team(match.id)

    assert remaining_ids(db_session) == survivors


def test_other_matches_are_not_touched(db_session, league_match):
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
    mine = substitute(db_session, match, teams[1])
    theirs = substitute(db_session, other, teams[1])
    mine_id, theirs_id = mine.id, theirs.id

    SqlAlchemySubstitutionRepository(db_session).delete_first_per_team(match.id)

    assert remaining_ids(db_session) == {theirs_id}
    assert mine_id not in remaining_ids(db_session)