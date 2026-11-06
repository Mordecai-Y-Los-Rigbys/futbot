from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session_service, get_substitution_service
from app.errors import ApiError
from app.main import app
from app.services.session_service import SessionService
from app.services.substitution_service import SubstitutionService


@pytest.fixture
def service():
    return create_autospec(SubstitutionService, instance=True)


@pytest.fixture
def client(service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: 7 if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_substitution_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_put_returns_204(client, service):
    client.cookies.set("session_id", "ok")
    response = client.put(
        "/matches/5/substitutions",
        json={"starterId": 10, "substituteId": 13},
    )
    assert response.status_code == 204
    service.request_substitution.assert_called_once_with(
        7, 5, {"starterId": 10, "substituteId": 13}
    )


@pytest.mark.parametrize("path", [
    "/matches/5/substitutions",
    "/matches/not-an-id/substitutions",
])
def test_401_precedes_route_id_and_body_validation(client, service, path):
    response = client.put(path, json={})
    assert response.status_code == 401
    assert response.json()["code"] is None
    service.request_substitution.assert_not_called()


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "2147483648"])
def test_invalid_route_id_is_404(client, service, bad_id):
    client.cookies.set("session_id", "ok")
    response = client.put(
        f"/matches/{bad_id}/substitutions",
        json={"starterId": "bad", "substituteId": None},
    )
    assert response.status_code == 404
    service.request_substitution.assert_not_called()


def test_missing_match_is_404(client, service):
    client.cookies.set("session_id", "ok")
    service.request_substitution.side_effect = ApiError(404, None, "El partido no existe.")
    response = client.put(
        "/matches/5/substitutions",
        json={"starterId": 10, "substituteId": 13},
    )
    assert response.status_code == 404
