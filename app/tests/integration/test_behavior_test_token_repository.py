from datetime import datetime, timedelta, timezone

import pytest

from app.models.behavior import Behavior
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository
from app.repositories.behavior_test_token_abstract import CreateBehaviorTestTokenData
from app.repositories.behavior_test_token_sqlalchemy import SqlAlchemyBehaviorTestTokenRepository
from app.domain.behavior import BehaviorType

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def behavior(db_session, create_user):
    record = Behavior(user_id=create_user("owner").id, name="b", code="pass")
    db_session.add(record)
    db_session.commit()
    return record


def test_saves_and_reads_the_token(db_session, behavior):
    repo = SqlAlchemyBehaviorTestTokenRepository(db_session)
    repo.create(
        CreateBehaviorTestTokenData(
            token="t1",
            user_id=behavior.user_id,
            behavior_id=behavior.id,
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )
    )

    data = repo.get_by_token("t1")
    assert (data.user_id, data.behavior_id) == (behavior.user_id, behavior.id)
    assert data.expires_at == NOW + timedelta(minutes=5)
    assert data.expires_at.tzinfo is not None


def test_unknown_token_is_none(db_session):
    assert SqlAlchemyBehaviorTestTokenRepository(db_session).get_by_token("nope") is None


def test_behavior_data_has_its_type(db_session, create_user):
    record = Behavior(
        user_id=create_user("coach").id, name="dt", code="pass", type=BehaviorType.coach_behavior
    )
    db_session.add(record)
    db_session.commit()
    assert SqlAlchemyBehaviorRepository(db_session).get_by_id(record.id).type == (
        BehaviorType.coach_behavior
    )