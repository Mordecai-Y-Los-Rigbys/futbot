import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.user_repository import UserRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def repo(db_session):
    return UserRepository(db_session)


def test_create_persists_and_assigns_an_id(repo):
    user = repo.create("messi", "messi@test.com", "hash", "Inter", 2)

    assert user.id is not None
    assert repo.get_by_email("messi@test.com").id == user.id


def test_get_by_email_unknown_returns_none(repo):
    assert repo.get_by_email("nadie@test.com") is None


def test_get_by_email_only_matches_the_exact_email(repo):
    repo.create("a", "a@test.com", "hash", "A", 1)
    repo.create("b", "b@test.com", "hash", "B", 1)

    assert repo.get_by_email("b@test.com").username == "b"


def test_duplicate_email_violates_the_unique_constraint(repo, db_session):
    repo.create("a", "dup@test.com", "hash", "A", 1)

    with pytest.raises(IntegrityError):
        repo.create("b", "dup@test.com", "hash", "B", 1)
    db_session.rollback()