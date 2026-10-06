from datetime import datetime, timedelta, timezone
from unittest.mock import create_autospec

import pytest
from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.repositories.session_abstract import CreateSessionData
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    return create_autospec(Session, instance=True)


@pytest.fixture
def repo(db):
    return SqlAlchemySessionRepository(db)


def record(expires_at=NOW + timedelta(hours=1)):
    return UserSession(id="sid", user_id=1, created_at=NOW, expires_at=expires_at)


def test_create_adds_commits_and_refreshes(repo, db):
    data = CreateSessionData(
        id="sid", user_id=1, created_at=NOW, expires_at=NOW + timedelta(hours=1)
    )

    result = repo.create(data)

    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert isinstance(added, UserSession)
    assert added.id == "sid"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(added)
    assert result.user_id == 1


def test_get_by_id_returns_none_when_missing(repo, db):
    db.get.return_value = None

    assert repo.get_by_id("nope") is None
    db.get.assert_called_once_with(UserSession, "nope")


def test_get_by_id_normalizes_naive_datetimes(repo, db):
    db.get.return_value = record(expires_at=datetime(2026, 1, 1, 13, 0))  # naive

    data = repo.get_by_id("sid")

    assert data.expires_at.tzinfo is not None


def test_delete_removes_and_commits_when_found(repo, db):
    rec = record()
    db.get.return_value = rec

    repo.delete("sid")

    db.delete.assert_called_once_with(rec)
    db.commit.assert_called_once()


def test_delete_does_nothing_when_missing(repo, db):
    db.get.return_value = None

    repo.delete("nope")

    db.delete.assert_not_called()
    db.commit.assert_not_called()
