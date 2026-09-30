# app/tests/unit/test_behavior_service_get.py
from unittest.mock import MagicMock

import pytest

from app.errors import ApiError
from app.models.behavior import Behavior
from app.services.behavior_service import BehaviorService


def make_service(behavior):
    db = MagicMock()
    db.get.return_value = behavior
    return BehaviorService(db), db


def test_returns_own_behavior():
    behavior = Behavior(id=5, user_id=1, name="a", code="x")
    service, db = make_service(behavior)

    result = service.get_owned_behavior(user_id=1, behavior_id=5)

    assert result is behavior
    db.get.assert_called_once_with(Behavior, 5)


def test_nonexistent_raises_404():
    service, _ = make_service(None)

    with pytest.raises(ApiError) as exc:
        service.get_owned_behavior(user_id=1, behavior_id=5)

    assert exc.value.status_code == 404
    assert exc.value.code is None


def test_other_users_behavior_raises_403():
    service, _ = make_service(Behavior(id=5, user_id=2, name="a", code="secreto"))

    with pytest.raises(ApiError) as exc:
        service.get_owned_behavior(user_id=1, behavior_id=5)

    assert exc.value.status_code == 403
    assert "secreto" not in exc.value.message


def test_is_read_only():
    service, db = make_service(Behavior(id=5, user_id=1, name="a", code="x"))

    service.get_owned_behavior(user_id=1, behavior_id=5)

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()