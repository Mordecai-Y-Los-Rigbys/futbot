from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session_service, get_substitution_service
from app.errors import ApiError
from app.main import app
from app.schemas.substitution import NextSubstitutions, SubstitutionResponse
from app.services.session_service import SessionService
from app.services.substitution_service import SubstitutionService


@pytest.fixture
def service():
    mock = create_autospec(SubstitutionService, instance=True)
    mock.get_next.return_value = NextSubstitutions(
        club1=SubstitutionResponse(starter_name="A", substitute_name="B"), club2=None
    )
    return mock


@pytest.fixture
def client(service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: 7 if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_substitution_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_success_is_camel_case_with_nulls(client, service):
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5/substitutions/next")
    assert r.status_code == 200
    assert r.json() == {
        "club1": {"starterName": "A", "substituteName": "B"},
        "club2": None,
    }
    service.get_next.assert_called_once_with(7, 5)


@pytest.mark.parametrize("path", ["/matches/5/substitutions/next", "/matches/abc/substitutions/next"])
def test_no_session_is_401_before_anything(client, service, path):
    r = client.get(path)
    assert r.status_code == 401 and r.json()["code"] is None
    service.get_next.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404(client, service, bad):
    client.cookies.set("session_id", "ok")
    r = client.get(f"/matches/{bad}/substitutions/next")
    assert r.status_code == 404
    service.get_next.assert_not_called()


def test_service_errors_pass_through(client, service):
    client.cookies.set("session_id", "ok")
    service.get_next.side_effect = ApiError(409, "matchNotStarted", "no")
    r = client.get("/matches/5/substitutions/next")
    assert (r.status_code, r.json()["code"]) == (409, "matchNotStarted")