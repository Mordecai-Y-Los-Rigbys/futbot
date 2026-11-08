from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_match_service, get_session_service
from app.main import app
from app.schemas.lineup import LineupPlayer, MatchLineups
from app.services.match_service import MatchService
from app.services.session_service import SessionService


def lineups(**fields) -> MatchLineups:
    base = dict(
        club1=[
            LineupPlayer(player_id=3, name="Delantero", role="forward"),
            LineupPlayer(player_id=2, name="Medio", role="midfield"),
            LineupPlayer(player_id=1, name="Defensor", role="defense"),
        ],
        club2=None,
    )
    return MatchLineups(**(base | fields))


@pytest.fixture
def service():
    mock = create_autospec(MatchService, instance=True)
    mock.get_lineups.return_value = lineups()
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
    response = client.get("/matches/5/lineups")
    assert response.status_code == 200
    assert response.json() == {
        "club1": [
            {"playerId": 3, "name": "Delantero", "role": "forward"},
            {"playerId": 2, "name": "Medio", "role": "midfield"},
            {"playerId": 1, "name": "Defensor", "role": "defense"},
        ],
        "club2": None,
    }
    service.get_lineups.assert_called_once_with(5, "ok", 7)


@pytest.mark.parametrize("path", ["/matches/5/lineups", "/matches/abc/lineups"])
def test_no_session_is_401_before_anything(client, service, path):
    response = client.get(path)
    assert response.status_code == 401 and response.json()["code"] is None
    service.get_lineups.assert_not_called()


@pytest.mark.parametrize("invalid_id", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404(client, service, invalid_id):
    client.cookies.set("session_id", "ok")
    response = client.get(f"/matches/{invalid_id}/lineups")
    assert response.status_code == 404 and response.json()["code"] is None
    service.get_lineups.assert_not_called()
