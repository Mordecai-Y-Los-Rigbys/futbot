from datetime import datetime, timedelta, timezone
from unittest.mock import create_autospec

import pytest

from app.domain.behavior import BehaviorType
from app.errors import ApiError
from app.repositories.behavior_abstract import BehaviorData
from app.services import behavior_test_connection_service as module
from app.services.behavior_service import BehaviorService
from app.services.behavior_test_connection_service import BehaviorTestConnectionService

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


class FakeTokens:
    def __init__(self):
        self.created = []

    def create(self, data):
        self.created.append(data)

    def get_by_token(self, token):
        return None


def behavior(type=BehaviorType.player_behavior):
    return BehaviorData(id=4, user_id=7, name="b", code="pass", type=type)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(module, "_utcnow", lambda: NOW)


@pytest.fixture()
def behaviors():
    service = create_autospec(BehaviorService, instance=True)
    service.get_owned_behavior.return_value = behavior()
    return service


@pytest.fixture()
def tokens():
    return FakeTokens()


def test_creates_a_token_tied_to_the_user_and_the_behavior(behaviors, tokens):
    token = BehaviorTestConnectionService(behaviors, tokens).connect(7, 4)

    behaviors.get_owned_behavior.assert_called_once_with(7, 4)
    [saved] = tokens.created
    assert saved.token == token
    assert (saved.user_id, saved.behavior_id) == (7, 4)
    assert saved.created_at == NOW
    assert saved.expires_at == NOW + timedelta(minutes=5)


def test_each_call_creates_a_new_token(behaviors, tokens):
    service = BehaviorTestConnectionService(behaviors, tokens)
    assert service.connect(7, 4) != service.connect(7, 4)


@pytest.mark.parametrize("status", [404, 403])
def test_errors_of_get_owned_behavior_propagate_without_a_token(behaviors, tokens, status):
    behaviors.get_owned_behavior.side_effect = ApiError(status, None, "x")
    with pytest.raises(ApiError) as exc:
        BehaviorTestConnectionService(behaviors, tokens).connect(7, 4)
    assert (exc.value.status_code, exc.value.code) == (status, None)
    assert tokens.created == []


def test_coach_behavior_is_409_without_a_token(behaviors, tokens):
    behaviors.get_owned_behavior.return_value = behavior(BehaviorType.coach_behavior)
    with pytest.raises(ApiError) as exc:
        BehaviorTestConnectionService(behaviors, tokens).connect(7, 4)
    assert (exc.value.status_code, exc.value.code) == (409, "notPlayerBehavior")
    assert tokens.created == []