from unittest.mock import create_autospec

import pytest

from app.api.deps import get_behavior_test_connection_service
from app.errors import ApiError
from app.main import app
from app.services.behavior_test_connection_service import BehaviorTestConnectionService

URL = "/behaviors/4/test-connections"


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
    resp = auth_api.post(URL)
    assert resp.status_code == 201
    assert resp.json() == {"tokenWs": "token-abc"}
    service.connect.assert_called_once_with(7, 4)


def test_the_body_is_ignored(auth_api):
    resp = auth_api.post(URL, content=b"{no es json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 201


@pytest.mark.parametrize("path", [URL, "/behaviors/abc/test-connections"])
def test_no_cookie_is_401_even_with_a_bad_id(api, service, path):
    resp = api.post(path)
    assert resp.status_code == 401 and resp.json()["code"] is None
    service.connect.assert_not_called()


@pytest.mark.parametrize("raw_id", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404_without_calling_the_service(auth_api, service, raw_id):
    resp = auth_api.post(f"/behaviors/{raw_id}/test-connections")
    assert resp.status_code == 404 and resp.json()["code"] is None
    service.connect.assert_not_called()


@pytest.mark.parametrize(
    "status, code", [(404, None), (403, None), (409, "notPlayerBehavior")]
)
def test_service_errors_are_returned(auth_api, service, status, code):
    service.connect.side_effect = ApiError(status, code, "x")
    resp = auth_api.post(URL)
    assert resp.status_code == status and resp.json()["code"] == code


def test_operation_id_is_in_the_openapi(api):
    assert api.get("/openapi.json").json()["paths"]["/behaviors/{id}/test-connections"]["post"][
        "operationId"
    ] == "testBehavior"