from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.behavior import BehaviorType
from app.models.behavior import Behavior
from app.models.behavior_test_token import BehaviorTestToken

pytestmark = pytest.mark.integration


@pytest.fixture()
def owner(create_user):
    return create_user("owner")


@pytest.fixture()
def make_behavior(db_session):
    def _make(user, type=BehaviorType.player_behavior):
        record = Behavior(user_id=user.id, name="b", code="pass", type=type)
        db_session.add(record)
        db_session.commit()
        return record

    return _make


def url(behavior_id):
    return f"/behaviors/{behavior_id}/test-connections"


def tokens_of(db_session):
    db_session.expire_all()
    return list(db_session.scalars(select(BehaviorTestToken)))


def test_201_saves_a_token_for_that_user_and_behavior(login_as, db_session, owner, make_behavior):
    behavior = make_behavior(owner)
    before = datetime.now(timezone.utc)

    resp = login_as(owner).post(url(behavior.id))
    assert resp.status_code == 201
    token = resp.json()["tokenWs"]

    [saved] = tokens_of(db_session)
    assert saved.token == token
    assert (saved.user_id, saved.behavior_id) == (owner.id, behavior.id)
    expires_at = saved.expires_at.replace(tzinfo=saved.expires_at.tzinfo or timezone.utc)
    assert before + timedelta(minutes=5) <= expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5)


def test_the_body_is_ignored(login_as, owner, make_behavior):
    behavior = make_behavior(owner)
    resp = login_as(owner).post(url(behavior.id), json={"behaviorId": 999})
    assert resp.status_code == 201


def test_no_session_is_401(client, owner, make_behavior):
    resp = client.post(url(make_behavior(owner).id))
    assert resp.status_code == 401 and resp.json()["code"] is None


def test_expired_session_is_401(login_as, owner, make_behavior):
    resp = login_as(owner, expires_in=timedelta(days=-1)).post(url(make_behavior(owner).id))
    assert resp.status_code == 401


@pytest.mark.parametrize("raw_id", ["2147483647", "abc", "0"])
def test_unknown_or_invalid_behavior_is_404(login_as, db_session, owner, raw_id):
    resp = login_as(owner).post(url(raw_id))
    assert resp.status_code == 404 and resp.json()["code"] is None
    assert tokens_of(db_session) == []


def test_behavior_of_another_user_is_403(login_as, db_session, owner, create_user, make_behavior):
    other = make_behavior(create_user("other"))
    resp = login_as(owner).post(url(other.id))
    assert resp.status_code == 403 and resp.json()["code"] is None
    assert tokens_of(db_session) == []


def test_coach_behavior_is_409(login_as, db_session, owner, make_behavior):
    coach = make_behavior(owner, BehaviorType.coach_behavior)
    resp = login_as(owner).post(url(coach.id))
    assert resp.status_code == 409 and resp.json()["code"] == "notPlayerBehavior"
    assert tokens_of(db_session) == []


def test_403_beats_409(login_as, owner, create_user, make_behavior):
    other_coach = make_behavior(create_user("other"), BehaviorType.coach_behavior)
    assert login_as(owner).post(url(other_coach.id)).status_code == 403


def test_401_beats_404(client):
    assert client.post(url("abc")).status_code == 401