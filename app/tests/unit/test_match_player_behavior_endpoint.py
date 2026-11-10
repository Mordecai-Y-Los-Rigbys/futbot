from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_match_player_behavior_service, get_session_service
from app.errors import ApiError, ValidationApiError
from app.main import app
from app.schemas.match_behavior import MatchPlayerBehavior
from app.services.match_player_behavior_service import MatchPlayerBehaviorService
from app.services.session_service import SessionService


@pytest.fixture
def service():
    mock = create_autospec(MatchPlayerBehaviorService, instance=True)
    mock.get_behavior.return_value = MatchPlayerBehavior(name="Atacante", code="move(1, 0)")
    return mock


@pytest.fixture
def client(service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: 7 if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_match_player_behavior_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_success_returns_name_and_code(client, service):
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5/behavior?playerId=3")
    assert r.status_code == 200
    assert r.json() == {"name": "Atacante", "code": "move(1, 0)"}
    service.get_behavior.assert_called_once_with(7, 5, "3")


@pytest.mark.parametrize(
    "query, raw",
    [("", None), ("?playerId=", ""), ("?playerId=abc", "abc"), ("?playerId=1.5", "1.5")],
)
def test_raw_player_id_reaches_the_service(client, service, query, raw):
    client.cookies.set("session_id", "ok")
    assert client.get(f"/matches/5/behavior{query}").status_code == 200
    service.get_behavior.assert_called_once_with(7, 5, raw)


@pytest.mark.parametrize("path", ["/matches/5/behavior?playerId=3", "/matches/abc/behavior"])
def test_no_session_is_401_before_anything(client, service, path):
    r = client.get(path)
    assert r.status_code == 401 and r.json()["code"] is None
    service.get_behavior.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_route_id_is_404_even_with_invalid_player_id(client, service, bad):
    client.cookies.set("session_id", "ok")
    r = client.get(f"/matches/{bad}/behavior?playerId=abc")
    assert r.status_code == 404
    service.get_behavior.assert_not_called()


@pytest.mark.parametrize(
    "error, status, code",
    [
        (ApiError(404, None, "x"), 404, None),
        (ValidationApiError([{"field": "playerId", "reason": "required"}]), 400, "invalidFields"),
        (ApiError(403, "notAPlayerInMatch", "x"), 403, "notAPlayerInMatch"),
        (ApiError(403, "playerNotStarter", "x"), 403, "playerNotStarter"),
    ],
)
def test_service_errors_keep_their_status_and_code(client, service, error, status, code):
    client.cookies.set("session_id", "ok")
    service.get_behavior.side_effect = error
    r = client.get("/matches/5/behavior?playerId=3")
    assert (r.status_code, r.json()["code"]) == (status, code)


def test_400_has_the_validation_format(client, service):
    client.cookies.set("session_id", "ok")
    service.get_behavior.side_effect = ValidationApiError(
        [{"field": "playerId", "reason": "outOfRange"}]
    )
    r = client.get("/matches/5/behavior?playerId=0")
    assert r.json()["errors"] == [{"field": "playerId", "reason": "outOfRange"}]
