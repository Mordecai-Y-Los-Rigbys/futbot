from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session_service, get_substitution_service
from app.errors import ApiError
from app.main import app
from app.schemas.substitution import Substitution, Substitutions
from app.services.session_service import SessionService
from app.services.substitution_service import SubstitutionService


@pytest.fixture
def service():
    mock = create_autospec(SubstitutionService, instance=True)
    mock.get_substitutions.return_value = Substitutions(
        club1=Substitution(starter_name="A", substitute_name="B"), club2=None
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
    r = client.get("/matches/5/substitutions")
    assert r.status_code == 200
    assert r.json() == {
        "club1": {"starterName": "A", "substituteName": "B"},
        "club2": None,
    }
    service.get_substitutions.assert_called_once_with(7, 5)


def test_the_old_next_path_no_longer_exists(client):
    client.cookies.set("session_id", "ok")
    assert client.get("/matches/5/substitutions/next").status_code == 404


@pytest.mark.parametrize("path", ["/matches/5/substitutions", "/matches/abc/substitutions"])
def test_no_session_is_401_before_anything(client, service, path):
    r = client.get(path)
    assert r.status_code == 401 and r.json()["code"] is None
    service.get_substitutions.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404(client, service, bad):
    client.cookies.set("session_id", "ok")
    r = client.get(f"/matches/{bad}/substitutions")
    assert r.status_code == 404
    service.get_substitutions.assert_not_called()


@pytest.mark.parametrize("code", ["matchNotStarted", "matchInPenalties", "noPausesLeft"])
def test_service_errors_pass_through(client, service, code):
    client.cookies.set("session_id", "ok")
    service.get_substitutions.side_effect = ApiError(409, code, "no")
    r = client.get("/matches/5/substitutions")
    assert (r.status_code, r.json()["code"]) == (409, code)
