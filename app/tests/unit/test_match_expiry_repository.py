import pytest

from app.models.match import Match, MatchStatus
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository

pytestmark = pytest.mark.integration


@pytest.fixture()
def users(make_user):
    return make_user(1), make_user(2)


@pytest.fixture()
def repo(db_session):
    return SqlAlchemyMatchExpiryRepository(db_session)


def add_match(db_session, **fields) -> Match:
    match = Match(**fields)
    db_session.add(match)
    db_session.commit()
    return match


def status_of(db_session, match) -> MatchStatus:
    db_session.refresh(match)
    return match.status


def test_waiting_friendly_is_cancelled(repo, db_session, users):
    match = add_match(db_session, user_1_id=1)

    assert repo.cancel_if_waiting_friendly(match.id) is True
    assert status_of(db_session, match) == MatchStatus.cancelled


def test_friendly_with_a_rival_is_not_cancelled(repo, db_session, users):
    # el rival se unió antes del vencimiento: gana la unión
    match = add_match(db_session, user_1_id=1, user_2_id=2)

    assert repo.cancel_if_waiting_friendly(match.id) is False
    assert status_of(db_session, match) == MatchStatus.scheduled


def test_started_match_is_not_cancelled(repo, db_session, users):
    match = add_match(db_session, user_1_id=1, user_2_id=2, status=MatchStatus.started)

    assert repo.cancel_if_waiting_friendly(match.id) is False
    assert status_of(db_session, match) == MatchStatus.started


def test_cancelling_twice_is_idempotent(repo, db_session, users):
    match = add_match(db_session, user_1_id=1)

    assert repo.cancel_if_waiting_friendly(match.id) is True
    assert repo.cancel_if_waiting_friendly(match.id) is False
    assert status_of(db_session, match) == MatchStatus.cancelled


def test_unknown_match_returns_false(repo, users):
    assert repo.cancel_if_waiting_friendly(999) is False


def test_list_waiting_friendlies_only_returns_waiting_ones(repo, db_session, users):
    waiting = add_match(db_session, user_1_id=1)
    add_match(db_session, user_1_id=1, user_2_id=2)  # con rival
    add_match(db_session, user_1_id=1, status=MatchStatus.cancelled)  # ya cancelado

    items = repo.list_waiting_friendlies()

    assert [i.match_id for i in items] == [waiting.id]
    assert items[0].created_at.tzinfo is not None