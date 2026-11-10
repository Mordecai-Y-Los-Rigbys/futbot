from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_behavior_service, get_session_service
from app.main import app
from app.services.behavior_service import BehaviorService
from app.services.session_service import SessionService


@pytest.fixture
def session_service():
    mock = create_autospec(SessionService, instance=True)
    mock.get_user_id.side_effect = lambda sid: (
        int(sid.removeprefix("sid-")) if sid.startswith("sid-") else None
    )
    return mock


@pytest.fixture
def behavior_service():
    mock = create_autospec(BehaviorService, instance=True)
    mock.delete_behavior.return_value = None
    return mock


@pytest.fixture
def client(session_service, behavior_service):
    app.dependency_overrides[get_session_service] = lambda: session_service
    app.dependency_overrides[get_behavior_service] = lambda: behavior_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_deleted_returns_204_without_body(client, behavior_service):
    client.cookies.set("session_id", "sid-7")

    response = client.delete("/behaviors/5")

    assert response.status_code == 204
    assert response.content == b""
    behavior_service.delete_behavior.assert_called_once_with(7, 5)


@pytest.mark.parametrize("bad_id", ["abc", "0", "2147483648"])
def test_an_invalid_id_is_404(client, behavior_service, bad_id):
    client.cookies.set("session_id", "sid-7")

    response = client.delete(f"/behaviors/{bad_id}")

    assert response.status_code == 404
    assert response.json()["code"] is None
    behavior_service.delete_behavior.assert_not_called()


def test_without_session_is_401_before_the_id(client, behavior_service):
    response = client.delete("/behaviors/abc")

    assert response.status_code == 401
    behavior_service.delete_behavior.assert_not_called()
