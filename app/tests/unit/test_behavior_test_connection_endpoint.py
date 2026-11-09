from unittest.mock import create_autospec

import pytest

from app.api.deps import get_behavior_test_connection_service
from app.errors import ApiError, ValidationApiError
from app.main import app
from app.services.behavior_test_connection_service import BehaviorTestConnectionService
from app.services.league_validation import INVALID_JSON

URL = "/behaviors/4/test-connections"
BODY = {"members": [{"playerId": 1, "club": "club1", "role": "forward", "behaviorId": 4}]}


@pytest.fixture()
def service():
    fake = create_autospec(BehaviorTestConnectionService, instance=True)
    fake.connect.return_value = "token-abc"
    app.dependency_overrides[get_behavior_test_connection_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_behavior_test_connection_service, None)


@pytest.fixture()
def auth_api(api, service):
    api.cookies.set("session_id", "valid-session")
    return api


def test_success_is_201_with_the_token(auth_api, service):
    resp = auth_api.post(URL, json=BODY)
    assert resp.status_code == 201
    assert resp.json() == {"tokenWs": "token-abc"}
    service.connect.assert_called_once_with(7, 4, BODY)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, None),
        ({"content": b"{no es json", "headers": {"Content-Type": "application/json"}}, INVALID_JSON),
        ({"json": [1]}, [1]),
    ],
    ids=["vacío", "json inválido", "no es un objeto"],
)
def test_the_raw_body_reaches_the_service_without_a_422(auth_api, service, kwargs, expected):
    assert auth_api.post(URL, **kwargs).status_code == 201
    assert service.connect.call_args.args[2] == expected


def test_validation_error_is_400_with_the_errors(auth_api, service):
    service.connect.side_effect = ValidationApiError([{"field": "members", "reason": "required"}])
    resp = auth_api.post(URL)
    assert resp.status_code == 400
    assert resp.json() == {
        "code": "invalidFields",
        "message": "Revisá los campos marcados.",
        "errors": [{"field": "members", "reason": "required"}],
    }


@pytest.mark.parametrize("path", [URL, "/behaviors/abc/test-connections"])
def test_no_cookie_is_401_even_with_a_bad_id_or_body(api, service, path):
    resp = api.post(path, json={"members": 5})
    assert resp.status_code == 401 and resp.json()["code"] is None
    service.connect.assert_not_called()


@pytest.mark.parametrize("raw_id", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404_without_calling_the_service(auth_api, service, raw_id):
    resp = auth_api.post(f"/behaviors/{raw_id}/test-connections", json={"members": 5})
    assert resp.status_code == 404 and resp.json()["code"] is None
    service.connect.assert_not_called()


@pytest.mark.parametrize(
    "status, code",
    [
        (404, None),
        (403, None),
        (409, "notPlayerBehavior"),
        (409, "playerOrBehaviorNotOwned"),
        (409, "behaviorTypeMismatch"),
    ],
)
def test_service_errors_are_returned(auth_api, service, status, code):
    service.connect.side_effect = ApiError(status, code, "x")
    resp = auth_api.post(URL, json=BODY)
    assert resp.status_code == status and resp.json()["code"] == code


def test_openapi_documents_the_body_and_the_errors(api):
    spec = api.get("/openapi.json").json()
    op = spec["paths"]["/behaviors/{id}/test-connections"]["post"]
    assert op["operationId"] == "testBehavior"
    assert op["requestBody"]["required"] is True
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    assert schema["required"] == ["members"]
    assert schema["properties"]["members"]["items"]["required"] == [
        "playerId",
        "club",
        "role",
        "behaviorId",
    ]
    assert {"201", "400", "401", "403", "404", "409"} <= set(op["responses"])
    assert spec["components"]["schemas"]["TestBehaviorConflict"]["properties"]["code"]["enum"] == [
        "notPlayerBehavior",
        "playerOrBehaviorNotOwned",
        "behaviorTypeMismatch",
    ]
