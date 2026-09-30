# tests/unit/test_session_service.py
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base  # adjust to the module where your Base lives
from app.models.session import UserSession
from app.services import session_service
from app.services.session_service import SessionService, SESSION_TTL


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def service(db):
    return SessionService(db)


# ---------- create ----------

def test_create_persists_the_session(service, db):
    s = service.create(user_id=1)
    assert db.get(UserSession, s.id) is not None


def test_create_assigns_user_id(service):
    s = service.create(user_id=42)
    assert s.user_id == 42


def test_create_generates_distinct_ids(service):
    ids = {service.create(user_id=1).id for _ in range(20)}
    assert len(ids) == 20


def test_create_id_fits_in_string_64(service):
    s = service.create(user_id=1)
    assert 0 < len(s.id) <= 64


def test_create_uses_default_ttl(service):
    s = service.create(user_id=1)
    expires = s.expires_at
    created = s.created_at
    assert expires - created == SESSION_TTL


def test_create_respects_custom_ttl(service):
    s = service.create(user_id=1, ttl=timedelta(minutes=5))
    assert s.expires_at - s.created_at == timedelta(minutes=5)


# ---------- get_user_id ----------

def test_get_user_id_valid_session(service):
    s = service.create(user_id=7)
    assert service.get_user_id(s.id) == 7


def test_get_user_id_nonexistent_session(service):
    assert service.get_user_id("does-not-exist") is None


def test_get_user_id_expired_session_returns_none(service):
    s = service.create(user_id=1, ttl=timedelta(seconds=-1))
    assert service.get_user_id(s.id) is None


def test_get_user_id_expired_session_is_deleted(service, db):
    s = service.create(user_id=1, ttl=timedelta(seconds=-1))
    sid = s.id
    service.get_user_id(sid)
    db.expire_all()
    assert db.get(UserSession, sid) is None


def test_get_user_id_valid_session_is_not_deleted(service, db):
    s = service.create(user_id=1)
    service.get_user_id(s.id)
    assert db.get(UserSession, s.id) is not None


def test_get_user_id_handles_naive_expires_at(service, db):
    """SQLite returns DateTime without tz; the service must treat it as UTC."""
    s = service.create(user_id=3, ttl=timedelta(hours=1))
    sid = s.id
    db.expire_all()  # force a reload from the DB (naive)
    assert service.get_user_id(sid) == 3


def test_get_user_id_uses_utcnow_to_expire(service, monkeypatch):
    s = service.create(user_id=1, ttl=timedelta(hours=1))
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    monkeypatch.setattr(session_service, "_utcnow", lambda: future)
    assert service.get_user_id(s.id) is None


def test_get_user_id_exactly_at_the_limit_is_expired(service, db, monkeypatch):
    s = service.create(user_id=1, ttl=timedelta(hours=1))
    limit = s.expires_at
    if limit.tzinfo is None:
        limit = limit.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(session_service, "_utcnow", lambda: limit)
    assert service.get_user_id(s.id) is None  # the code uses <=


# ---------- delete ----------

def test_delete_removes_the_session(service, db):
    s = service.create(user_id=1)
    sid = s.id
    service.delete(sid)
    assert db.get(UserSession, sid) is None
    assert service.get_user_id(sid) is None


def test_delete_nonexistent_does_not_fail(service):
    service.delete("does-not-exist")  # must not raise


def test_delete_does_not_affect_other_sessions(service):
    a = service.create(user_id=1)
    b = service.create(user_id=2)
    service.delete(a.id)
    assert service.get_user_id(b.id) == 2