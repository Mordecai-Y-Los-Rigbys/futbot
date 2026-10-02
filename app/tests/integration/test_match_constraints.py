from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.league import League, LeagueStatus
from app.models.match import Match, MatchStatus

pytestmark = pytest.mark.integration

S, ST, F = MatchStatus.scheduled, MatchStatus.started, MatchStatus.finished
DATE = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


@pytest.fixture()
def users(make_user):
    return make_user(1), make_user(2)


@pytest.fixture()
def league(db_session, users):
    league = League(
        name="Liga",
        creator_id=users[0].id,
        status=LeagueStatus.started,
        min_participants=3,
        max_participants=8,
        match_duration=5,
        private=False,
    )
    db_session.add(league)
    db_session.commit()
    return league


def insert(db_session, **fields):
    db_session.add(Match(**fields))
    db_session.commit()


# --- combinaciones válidas ------------------------------------------------------------

def test_friendly_waiting_for_a_rival(db_session, users):
    insert(db_session, user_1_id=users[0].id)  # sin usuario 2, sin fecha, sin liga
    match = db_session.query(Match).one()
    assert match.status == MatchStatus.scheduled  # default
    assert match.user_2_id is None


def test_friendly_with_rival_in_every_status(db_session, users):
    insert(db_session, user_1_id=1, user_2_id=2, status=S)
    insert(db_session, user_1_id=1, user_2_id=2, status=ST)
    insert(db_session, user_1_id=1, user_2_id=2, status=F, score_1=2, score_2=2)


def test_league_match_with_date(db_session, users, league):
    insert(db_session, league_id=league.id, user_1_id=1, user_2_id=2, scheduled_at=DATE)


def test_zero_zero_is_a_valid_result(db_session, users):
    insert(db_session, user_1_id=1, user_2_id=2, status=F, score_1=0, score_2=0)


def test_deleting_the_league_deletes_its_matches(db_session, users, league):
    insert(db_session, league_id=league.id, user_1_id=1, user_2_id=2, scheduled_at=DATE)
    db_session.delete(league)
    db_session.commit()
    assert db_session.query(Match).count() == 0


# --- combinaciones inválidas ---------------------------------------------------------------

INVALID = [
    pytest.param(dict(user_1_id=1, user_2_id=1), id="juega contra sí mismo"),
    pytest.param(dict(user_1_id=1, status=ST), id="started sin rival"),
    pytest.param(dict(user_1_id=1, status=F, score_1=1, score_2=0), id="finished sin rival"),
    pytest.param(dict(user_1_id=1, user_2_id=2, status=F), id="finished sin resultado"),
    pytest.param(dict(user_1_id=1, user_2_id=2, status=F, score_1=1), id="finished con un solo score"),
    pytest.param(dict(user_1_id=1, user_2_id=2, status=ST, score_1=1, score_2=0), id="resultado en un partido que no terminó"),
    pytest.param(dict(user_1_id=1, user_2_id=2, status=S, score_1=1), id="un solo score"),
    pytest.param(dict(user_1_id=1, user_2_id=2, status=F, score_1=-1, score_2=0), id="score negativo"),
]

@pytest.mark.parametrize("fields", INVALID)
def test_invalid_combinations_are_rejected(db_session, users, fields):
    db_session.add(Match(**fields))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_league_match_without_date_is_rejected(db_session, users, league):
    db_session.add(Match(league_id=league.id, user_1_id=1, user_2_id=2))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_1_is_required(db_session, users):
    db_session.add(Match(user_2_id=2))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()