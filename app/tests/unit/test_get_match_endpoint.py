from datetime import datetime, timezone
from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_match_service, get_session_service
from app.errors import ApiError
from app.main import app
from app.schemas.friendly import MatchClub, MatchResponse
from app.services.match_service import MatchService
from app.services.session_service import SessionService


def response(**fields) -> MatchResponse:
    base = dict(
        id=5,
        league_id=9,
        name=None,
        status="started",
        club1=MatchClub(id=1, username="u1", name="c1", avatar=2),
        club2=MatchClub(id=2, username="u2", name="c2", avatar=4),
        scheduled_at=datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc),
        result=None,
    )
    return MatchResponse(**(base | fields))


@pytest.fixture
def service():
    mock = create_autospec(MatchService, instance=True)
    mock.get_match.return_value = response()
    return mock


@pytest.fixture
def client(service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: 7 if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_match_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_success_is_camel_case(client, service):
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5")
    assert r.status_code == 200
    assert r.json() == {
        "id": 5,
        "leagueId": 9,
        "name": None,
        "status": "started",
        "club1": {"id": 1, "username": "u1", "name": "c1", "avatar": 2},
        "club2": {"id": 2, "username": "u2", "name": "c2", "avatar": 4},
        "scheduledAt": "2026-11-20T18:00:00Z",
        "createdAt": "2026-11-05T12:00:00Z",
        "result": None,
    }
    service.get_match.assert_called_once_with(5, "ok", 7)


@pytest.mark.parametrize(
    "scheduled_at, expected",
    [
        (datetime(2026, 11, 20, 18, 0), "2026-11-20T18:00:00Z"),  # sin zona: se asume UTC
        (None, None),  # amistoso
    ],
)
def test_scheduled_at_is_utc_or_null(client, service, scheduled_at, expected):
    service.get_match.return_value = response(scheduled_at=scheduled_at)
    client.cookies.set("session_id", "ok")
    assert client.get("/matches/5").json()["scheduledAt"] == expected


@pytest.mark.parametrize("path", ["/matches/5", "/matches/abc"])
def test_no_session_is_401_before_anything(client, service, path):
    r = client.get(path)
    assert r.status_code == 401 and r.json()["code"] is None
    service.get_match.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404(client, service, bad):
    client.cookies.set("session_id", "ok")
    r = client.get(f"/matches/{bad}")
    assert r.status_code == 404 and r.json()["code"] is None
    service.get_match.assert_not_called()


@pytest.mark.parametrize(
    "status, code",
    [(404, None), (403, "notAPlayerInMatch"), (403, "leagueAccessRequired")],
)
def test_service_errors_pass_through(client, service, status, code):
    service.get_match.side_effect = ApiError(status, code, "x")
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5")
    assert (r.status_code, r.json()["code"]) == (status, code)
