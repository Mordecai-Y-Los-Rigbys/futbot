from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.match import Match, MatchStatus
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository


@pytest.fixture()
def db():
    return MagicMock(spec=Session)


@pytest.fixture()
def repo(db):
    return SqlAlchemyMatchRepository(db)


def test_returns_none_when_the_match_does_not_exist(repo, db):
    db.get.return_value = None
    assert repo.get_state(99) is None
    db.get.assert_called_once_with(Match, 99)


@pytest.mark.parametrize(
    "status, finished",
    [
        (MatchStatus.scheduled, False),
        (MatchStatus.started, False),
        (MatchStatus.finished, True),
    ],
)
def test_finished_flag_follows_the_status(repo, db, status, finished):
    db.get.return_value = SimpleNamespace(id=5, status=status)
    state = repo.get_state(5)
    assert (state.id, state.finished) == (5, finished)


def test_is_read_only(repo, db):
    db.get.return_value = SimpleNamespace(id=5, status=MatchStatus.finished)
    repo.get_state(5)
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()