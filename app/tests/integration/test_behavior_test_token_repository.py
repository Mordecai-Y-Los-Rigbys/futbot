from datetime import datetime, timedelta, timezone

import pytest

from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole
from app.models.behavior import Behavior
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository
from app.repositories.behavior_test_token_abstract import (
    BehaviorTestMemberData,
    CreateBehaviorTestTokenData,
)
from app.repositories.behavior_test_token_sqlalchemy import SqlAlchemyBehaviorTestTokenRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
LINEUP = [
    ("club1", "forward"),
    ("club1", "midfield"),
    ("club1", "defense"),
    ("club2", "forward"),
    ("club2", "midfield"),
    ("club2", "defense"),
]


@pytest.fixture()
def behavior(db_session, create_user):
    record = Behavior(user_id=create_user("owner").id, name="b", code="pass")
    db_session.add(record)
    db_session.commit()
    return record


def test_saves_and_reads_the_token_with_its_lineup(db_session, behavior):
    members = [
        BehaviorTestMemberData(
            player_id=10 + i, club=club, role=MemberRole(role), behavior_id=behavior.id
        )
        for i, (club, role) in enumerate(LINEUP)
    ]
    repo = SqlAlchemyBehaviorTestTokenRepository(db_session)
    repo.create(
        CreateBehaviorTestTokenData(
            token="t1",
            user_id=behavior.user_id,
            behavior_id=behavior.id,
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            members=members,
        )
    )

    data = repo.get_by_token("t1")
    assert (data.user_id, data.behavior_id) == (behavior.user_id, behavior.id)
    assert data.expires_at == NOW + timedelta(minutes=5)
    assert data.expires_at.tzinfo is not None
    assert data.members == members


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
