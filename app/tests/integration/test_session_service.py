from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.session import UserSession
from app.models.user import User
from app.repositories.session_abstract import CreateSessionData
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.services.session_service import SESSION_TTL

pytestmark = pytest.mark.integration


@pytest.fixture
def user(db_session):
    u = User(
        username="pguser",
        email="pg@test.com",
        password_hash="x",
        club_name="club",
        avatar=1,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def repository(db_session):
    return SqlAlchemySessionRepository(db_session)


# ---------- service + real DB ----------

def test_full_flow_with_real_fk(session_service, user):
    s = session_service.create(user_id=user.id)

    assert session_service.get_user_id(s.id) == user.id
    session_service.delete(s.id)
    assert session_service.get_user_id(s.id) is None


def test_create_persists_the_row(session_service, db_session, user):
    s = session_service.create(user_id=user.id)

    row = db_session.get(UserSession, s.id)
    assert row is not None
    assert row.user_id == user.id


def test_create_persists_default_ttl(session_service, user):
    s = session_service.create(user_id=user.id)

    assert s.expires_at - s.created_at == SESSION_TTL


def test_expired_session_returns_none_and_is_deleted(session_service, db_session, user):
    s = session_service.create(user_id=user.id, ttl=timedelta(seconds=-1))
    sid = s.id
    db_session.expire_all()

    assert session_service.get_user_id(sid) is None

    db_session.expire_all()
    assert db_session.get(UserSession, sid) is None


def test_valid_session_is_not_deleted(session_service, db_session, user):
    s = session_service.create(user_id=user.id)

    session_service.get_user_id(s.id)

    db_session.expire_all()
    assert db_session.get(UserSession, s.id) is not None


def test_delete_removes_the_row(session_service, db_session, user):
    s = session_service.create(user_id=user.id)

    session_service.delete(s.id)

    db_session.expire_all()
    assert db_session.get(UserSession, s.id) is None


def test_delete_nonexistent_does_not_fail(session_service):
    session_service.delete("does-not-exist")  # no tiene que fallar

def test_delete_does_not_affect_other_sessions(session_service, user):
    a = session_service.create(user_id=user.id)
    b = session_service.create(user_id=user.id)

    session_service.delete(a.id)

    assert session_service.get_user_id(b.id) == user.id


def test_cannot_create_session_for_nonexistent_user(session_service, db_session):
    with pytest.raises(IntegrityError):
        session_service.create(user_id=999999)
    db_session.rollback()


# ---------- repository: persistence details ----------

def test_repository_get_by_id_unknown_returns_none(repository):
    assert repository.get_by_id("does-not-exist") is None


def test_repository_returns_timezone_aware_datetimes(repository, db_session, user):
    # Se inserta con datetimes sin zona horaria, como los devolvería una columna DateTime sin tz
    naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        UserSession(
            id="naive",
            user_id=user.id,
            created_at=naive_now,
            expires_at=naive_now + timedelta(hours=1),
        )
    )
    db_session.commit()
    db_session.expire_all()

    data = repository.get_by_id("naive")

    assert data.created_at.tzinfo is not None
    assert data.expires_at.tzinfo is not None


def test_naive_expires_at_is_handled_by_the_service(session_service, db_session, user):
    naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        UserSession(
            id="naive-valid",
            user_id=user.id,
            created_at=naive_now,
            expires_at=naive_now + timedelta(hours=1),
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert session_service.get_user_id("naive-valid") == user.id


def test_repository_create_then_get_roundtrip(repository, user):
    now = datetime.now(timezone.utc)
    repository.create(
        CreateSessionData(
            id="rt", user_id=user.id, created_at=now, expires_at=now + timedelta(hours=1)
        )
    )

    data = repository.get_by_id("rt")

    assert data.user_id == user.id
    assert data.expires_at > data.created_at