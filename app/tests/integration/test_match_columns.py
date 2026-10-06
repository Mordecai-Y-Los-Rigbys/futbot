"""Columnas del contrato que tiene el partido: `name` (amistosos) y `createdAt`."""

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.models.match import Match

pytestmark = pytest.mark.integration


def test_name_longer_than_20_chars_is_rejected(db_session, make_user):
    make_user(1)
    db_session.add(Match(user_1_id=1, name="x" * 21))
    with pytest.raises((DataError, IntegrityError)):
        db_session.commit()
    db_session.rollback()


def test_created_at_is_filled_by_the_database(db_session, make_user):
    make_user(1)
    match = Match(user_1_id=1)
    db_session.add(match)
    db_session.commit()
    assert match.created_at is not None
