from unittest.mock import create_autospec

import pytest
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.repositories.behavior_abstract import BehaviorData
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository


@pytest.fixture
def db():
    return create_autospec(Session, instance=True)


@pytest.fixture
def repo(db):
    return SqlAlchemyBehaviorRepository(db)


def test_get_by_id_returns_none_when_missing(repo, db):
    db.get.return_value = None

    assert repo.get_by_id(5) is None
    db.get.assert_called_once_with(Behavior, 5)


def test_get_by_id_maps_record_to_data(repo, db):
    db.get.return_value = Behavior(id=5, user_id=2, name="a", code="x")

    assert repo.get_by_id(5) == BehaviorData(id=5, user_id=2, name="a", code="x")


def test_get_by_id_does_not_write(repo, db):
    db.get.return_value = Behavior(id=5, user_id=2, name="a", code="x")

    repo.get_by_id(5)

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
