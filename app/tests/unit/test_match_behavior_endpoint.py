from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_match_behavior_service, get_session_service
from app.errors import ApiError, ValidationApiError
from app.main import app
from app.services.league_validation import INVALID_JSON
from app.services.match_behavior_service import MatchBehaviorService
from app.services.session_service import SessionService

BODY = {"playerId": 3, "behaviorId": 7}


@pytest.fixture
def service():
    return create_autospec(MatchBehaviorService, instance=True)


@pytest.fixture
def client(service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: 7 if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_match_behavior_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_valid_request_is_204_without_body(client, service):
    client.cookies.set("session_id", "ok")
    r = client.put("/matches/5/behavior", json=BODY)
    assert r.status_code == 204 and r.content == b""
    service.reassign.assert_called_once_with(7, 5, BODY)


@pytest.mark.parametrize("path", ["/matches/5/behavior", "/matches/abc/behavior"])
def test_no_session_is_401_before_anything(client, service, path):
    r = client.put(path, json=BODY)
    assert r.status_code == 401 and r.json()["code"] is None
    service.reassign.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "2147483648"])
def test_invalid_id_is_404(client, service, bad):
    client.cookies.set("session_id", "ok")
    assert client.put(f"/matches/{bad}/behavior", json=BODY).status_code == 404
    service.reassign.assert_not_called()


def test_unparseable_body_reaches_the_service_as_invalid_json(client, service):
    client.cookies.set("session_id", "ok")
    client.put("/matches/5/behavior", content="{", headers={"Content-Type": "application/json"})
    service.reassign.assert_called_once_with(7, 5, INVALID_JSON)


@pytest.mark.parametrize(
    "error, status, code",
    [
        (ValidationApiError([{"field": "playerId", "reason": "required"}]), 400, "invalidFields"),
        (ApiError(403, "playerNotStarter", "x"), 403, "playerNotStarter"),
        (ApiError(409, "matchNotInProgress", "x"), 409, "matchNotInProgress"),
    ],
)
def test_service_errors_keep_their_status_and_code(client, service, error, status, code):
    client.cookies.set("session_id", "ok")
    service.reassign.side_effect = error
    r = client.put("/matches/5/behavior", json=BODY)
    assert (r.status_code, r.json()["code"]) == (status, code)