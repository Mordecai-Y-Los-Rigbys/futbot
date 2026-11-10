from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_behavior_service, get_session_service
from app.domain.behavior import BehaviorType
from app.main import app
from app.schemas.behavior import BehaviorDetail
from app.services.behavior_service import BehaviorService
from app.services.session_service import SessionService

BODY = {"name": "nuevo", "code": "x = ball_position()"}


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
    mock.update_behavior.return_value = BehaviorDetail(
        id=5,
        name="nuevo",
        code="x = ball_position()",
        type=BehaviorType.coach_behavior,
        deletable=False,
    )
    return mock


@pytest.fixture
def client(session_service, behavior_service):
    app.dependency_overrides[get_session_service] = lambda: session_service
    app.dependency_overrides[get_behavior_service] = lambda: behavior_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_updated_returns_200_with_the_detail_in_camel_case(client, behavior_service):
    client.cookies.set("session_id", "sid-7")

    response = client.put("/behaviors/5", json=BODY)

    assert response.status_code == 200
    assert response.json() == {
        "id": 5,
        "name": "nuevo",
        "type": "coachBehavior",
        "code": "x = ball_position()",
        "deletable": False,
    }
    behavior_service.update_behavior.assert_called_once_with(7, 5, BODY)


@pytest.mark.parametrize("bad_id", ["abc", "0", "2147483648"])
def test_an_invalid_id_is_404_not_found_before_the_body(client, behavior_service, bad_id):
    client.cookies.set("session_id", "sid-7")

    response = client.put(f"/behaviors/{bad_id}", content="{roto")

    assert response.status_code == 404
    assert response.json()["code"] == "notFound"
    behavior_service.update_behavior.assert_not_called()


def test_without_session_is_401_before_the_id(client, behavior_service):
    response = client.put("/behaviors/abc", json=BODY)

    assert response.status_code == 401
    behavior_service.update_behavior.assert_not_called()
