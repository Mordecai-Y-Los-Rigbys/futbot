from datetime import datetime, timedelta, timezone
from unittest.mock import create_autospec

import pytest

from app.repositories.session_abstract import (
    AbstractSessionRepository,
    CreateSessionData,
    SessionData,
)
from app.services import session_service
from app.services.session_service import SESSION_TTL, SessionService

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(session_service, "_utcnow", lambda: NOW)


@pytest.fixture
def repo():
    mock = create_autospec(AbstractSessionRepository, instance=True)
    mock.create.side_effect = lambda data: SessionData(**data.model_dump())
    return mock


@pytest.fixture
def service(repo):
    return SessionService(repo)


def stored_session(expires_at, user_id=1, session_id="sid"):
    return SessionData(
        id=session_id,
        user_id=user_id,
        created_at=NOW - timedelta(days=1),
        expires_at=expires_at,
    )


# ---------- create ----------

def test_create_calls_repository_once_with_create_data(service, repo):
    service.create(user_id=42)

    repo.create.assert_called_once()
    data = repo.create.call_args.args[0]
    assert isinstance(data, CreateSessionData)
    assert data.user_id == 42


def test_create_returns_what_the_repository_returns(service, repo):
    expected = stored_session(NOW + timedelta(days=7), user_id=9, session_id="from-repo")
    repo.create.side_effect = None
    repo.create.return_value = expected

    assert service.create(user_id=9) is expected


def test_create_generates_distinct_ids(service, repo):
    for _ in range(20):
        service.create(user_id=1)

    ids = {call.args[0].id for call in repo.create.call_args_list}
    assert len(ids) == 20


def test_create_id_fits_in_string_64(service, repo):
    service.create(user_id=1)

    assert 0 < len(repo.create.call_args.args[0].id) <= 64


def test_create_uses_default_ttl(service, repo):
    service.create(user_id=1)

    data = repo.create.call_args.args[0]
    assert data.created_at == NOW
    assert data.expires_at - data.created_at == SESSION_TTL


def test_create_respects_custom_ttl(service, repo):
    service.create(user_id=1, ttl=timedelta(minutes=5))

    data = repo.create.call_args.args[0]
    assert data.expires_at - data.created_at == timedelta(minutes=5)


# ---------- get_user_id ----------

def test_get_user_id_queries_the_repository_by_id(service, repo):
    repo.get_by_id.return_value = None

    service.get_user_id("abc")

    repo.get_by_id.assert_called_once_with("abc")


def test_get_user_id_valid_session(service, repo):
    repo.get_by_id.return_value = stored_session(NOW + timedelta(hours=1), user_id=7)

    assert service.get_user_id("sid") == 7


def test_get_user_id_valid_session_is_not_deleted(service, repo):
    repo.get_by_id.return_value = stored_session(NOW + timedelta(hours=1))

    service.get_user_id("sid")

    repo.delete.assert_not_called()


def test_get_user_id_nonexistent_session(service, repo):
    repo.get_by_id.return_value = None

    assert service.get_user_id("does-not-exist") is None
    repo.delete.assert_not_called()


def test_get_user_id_expired_session_returns_none(service, repo):
    repo.get_by_id.return_value = stored_session(NOW - timedelta(seconds=1))

    assert service.get_user_id("sid") is None


def test_get_user_id_expired_session_is_deleted(service, repo):
    repo.get_by_id.return_value = stored_session(NOW - timedelta(seconds=1))

    service.get_user_id("sid")

    repo.delete.assert_called_once_with("sid")


def test_get_user_id_exactly_at_the_limit_is_expired(service, repo):
    repo.get_by_id.return_value = stored_session(NOW) 

    assert service.get_user_id("sid") is None
    repo.delete.assert_called_once_with("sid")


def test_get_user_id_one_second_before_the_limit_is_valid(service, repo):
    repo.get_by_id.return_value = stored_session(NOW + timedelta(seconds=1), user_id=5)

    assert service.get_user_id("sid") == 5


# ---------- delete ----------

def test_delete_delegates_to_the_repository(service, repo):
    service.delete("sid")

    repo.delete.assert_called_once_with("sid")


def test_delete_does_not_read_or_create(service, repo):
    service.delete("sid")

    repo.get_by_id.assert_not_called()
    repo.create.assert_not_called()