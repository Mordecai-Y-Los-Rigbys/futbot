from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_behavior_service, get_session_service
from app.domain.behavior import BehaviorType
from app.errors import BehaviorConflictError
from app.main import app
from app.schemas.behavior import BehaviorDetail
from app.services.behavior_service import BehaviorService
from app.services.field_validation import INVALID_JSON
from app.services.session_service import SessionService

URL = "/behaviors"
BODY = {"name": "nuevo", "code": "go_to(1, 2)", "type": "coachBehavior"}


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
    mock.create_behavior.return_value = BehaviorDetail(
        id=9, name="nuevo", code="go_to(1, 2)", type=BehaviorType.coach_behavior, deletable=True
    )
    return mock


@pytest.fixture
def client(session_service, behavior_service):
    app.dependency_overrides[get_session_service] = lambda: session_service
    app.dependency_overrides[get_behavior_service] = lambda: behavior_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_created_returns_201_with_the_detail_in_camel_case(client, behavior_service):
    client.cookies.set("session_id", "sid-7")

    r = client.post(URL, json=BODY)

    assert r.status_code == 201
    assert r.json() == {
        "id": 9,
        "name": "nuevo",
        "type": "coachBehavior",
        "code": "go_to(1, 2)",
        "deletable": True,
    }
    behavior_service.create_behavior.assert_called_once_with(7, BODY)


def test_broken_json_reaches_the_service_as_invalid_json(client, behavior_service):
    client.cookies.set("session_id", "sid-7")

    client.post(URL, content="{roto", headers={"Content-Type": "application/json"})

    behavior_service.create_behavior.assert_called_once_with(7, INVALID_JSON)


def test_without_session_is_401_before_reading_the_body(client, behavior_service):
    r = client.post(URL, content="{roto", headers={"Content-Type": "application/json"})

    assert r.status_code == 401
    behavior_service.create_behavior.assert_not_called()


def test_a_conflict_has_code_message_and_code_error(client, behavior_service):
    client.cookies.set("session_id", "sid-7")
    code_error = {"rule": "callNotAllowed", "line": 1, "column": 1}
    behavior_service.create_behavior.side_effect = BehaviorConflictError(
        "invalidCode", "Línea 1, columna 1: ...", code_error
    )

    r = client.post(URL, json=BODY)

    assert r.status_code == 409
    assert r.json() == {
        "code": "invalidCode",
        "message": "Línea 1, columna 1: ...",
        "codeError": code_error,
    }


def test_a_conflict_without_location_has_code_error_null(client, behavior_service):
    client.cookies.set("session_id", "sid-7")
    behavior_service.create_behavior.side_effect = BehaviorConflictError("duplicateName", "...")

    r = client.post(URL, json=BODY)

    assert r.status_code == 409
    assert r.json()["codeError"] is None
