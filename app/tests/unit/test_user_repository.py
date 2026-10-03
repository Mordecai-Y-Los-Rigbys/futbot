from unittest.mock import create_autospec

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.fixture
def db():
    return create_autospec(Session, instance=True)


@pytest.fixture
def repo(db):
    return UserRepository(db)


def a_user(**over):
    data = dict(id=1, username="messi", email="messi@test.com",
                password_hash="h", club_name="Inter", avatar=1)
    data.update(over)
    return User(**data)


# ---------- get_by_email ----------

def test_get_by_email_returns_the_user_found(repo, db):
    found = a_user()
    db.query.return_value.filter.return_value.first.return_value = found

    assert repo.get_by_email("messi@test.com") is found
    db.query.assert_called_once_with(User)


def test_get_by_email_returns_none_when_missing(repo, db):
    db.query.return_value.filter.return_value.first.return_value = None

    assert repo.get_by_email("nadie@test.com") is None


def test_get_by_email_filters_by_the_given_email(repo, db):
    repo.get_by_email("messi@test.com")

    criterion = db.query.return_value.filter.call_args.args[0]
    assert "users.email" in str(criterion)
    assert criterion.right.value == "messi@test.com"  # bind parameter, no interpolación


def test_get_by_email_does_not_write(repo, db):
    repo.get_by_email("messi@test.com")

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


# ---------- create ----------

def test_create_adds_commits_and_refreshes_in_order(repo, db):
    repo.create("messi", "messi@test.com", "hash", "Inter", 2)

    assert [c[0] for c in db.method_calls] == ["add", "commit", "refresh"]


def test_create_builds_the_user_with_the_given_fields(repo, db):
    result = repo.create("messi", "messi@test.com", "hash", "Inter", 2)

    added = db.add.call_args.args[0]
    assert isinstance(added, User)
    assert (added.username, added.email, added.password_hash,
            added.club_name, added.avatar) == ("messi", "messi@test.com", "hash", "Inter", 2)
    db.refresh.assert_called_once_with(added)
    assert result is added


def test_create_does_not_swallow_commit_errors(repo, db):
    db.commit.side_effect = RuntimeError("falló el commit")

    with pytest.raises(RuntimeError):
        repo.create("messi", "messi@test.com", "hash", "Inter", 2)

    db.refresh.assert_not_called()