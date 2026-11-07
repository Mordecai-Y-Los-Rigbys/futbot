from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_match_team_service, get_session_service
from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole
from app.errors import ApiError
from app.main import app
from app.schemas.match_team import MatchTeam, MatchTeamMember, TeamBehavior
from app.services.match_team_service import MatchTeamService
from app.services.session_service import SessionService

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


def make_team(coach=True):
    return MatchTeam(
        members=[
            MatchTeamMember(
                player_id=10 + i,
                name=f"J{i}",
                role=MemberRole(role),
                behavior=TeamBehavior(id=3, name="Atacante", type=BehaviorType.player_behavior),
            )
            for i, role in enumerate(ROLES)
        ],
        coach_behavior=(
            TeamBehavior(id=9, name="DT ofensivo", type=BehaviorType.coach_behavior)
            if coach
            else None
        ),
    )


@pytest.fixture
def service():
    mock = create_autospec(MatchTeamService, instance=True)
    mock.get_team.return_value = make_team()
    return mock


@pytest.fixture
def client(service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: 7 if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_match_team_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_success_is_camel_case_and_matches_the_contract(client, service):
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5/team")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"members", "coachBehavior"}
    assert [m["role"] for m in body["members"]] == ROLES
    assert body["members"][0] == {
        "playerId": 10,
        "name": "J0",
        "role": "forward",
        "behavior": {"id": 3, "name": "Atacante", "type": "playerBehavior"},
    }
    assert body["coachBehavior"] == {"id": 9, "name": "DT ofensivo", "type": "coachBehavior"}
    service.get_team.assert_called_once_with(7, 5)


def test_member_does_not_expose_the_behavior_code(client):
    client.cookies.set("session_id", "ok")
    body = client.get("/matches/5/team").json()
    assert all("code" not in m["behavior"] for m in body["members"])


def test_coach_behavior_is_null_when_the_team_has_no_dt(client, service):
    service.get_team.return_value = make_team(coach=False)
    client.cookies.set("session_id", "ok")
    body = client.get("/matches/5/team").json()
    assert "coachBehavior" in body and body["coachBehavior"] is None


@pytest.mark.parametrize("path", ["/matches/5/team", "/matches/abc/team"])
def test_no_session_is_401_before_anything(client, service, path):
    r = client.get(path)
    assert r.status_code == 401 and r.json()["code"] is None
    service.get_team.assert_not_called()


def test_invalid_session_cookie_is_401(client, service):
    client.cookies.set("session_id", "expired")
    assert client.get("/matches/5/team").status_code == 401
    service.get_team.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648", "%20"])
def test_invalid_id_is_404(client, service, bad):
    client.cookies.set("session_id", "ok")
    r = client.get(f"/matches/{bad}/team")
    assert r.status_code == 404
    service.get_team.assert_not_called()


def test_missing_match_is_404(client, service):
    service.get_team.side_effect = ApiError(404, None, "El partido no existe.")
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5/team")
    assert (r.status_code, r.json()["code"]) == (404, None)


def test_not_a_player_is_403_with_code(client, service):
    service.get_team.side_effect = ApiError(403, "notAPlayerInMatch", "no")
    client.cookies.set("session_id", "ok")
    r = client.get("/matches/5/team")
    assert (r.status_code, r.json()["code"]) == (403, "notAPlayerInMatch")


def test_body_and_query_are_ignored(client, service):
    client.cookies.set("session_id", "ok")
    r = client.request("GET", "/matches/5/team?playerId=abc&x=1", content=b"{no json")
    assert r.status_code == 200
    service.get_team.assert_called_once_with(7, 5)


def test_only_get_is_allowed(client):
    client.cookies.set("session_id", "ok")
    assert client.post("/matches/5/team").status_code == 405
    assert client.put("/matches/5/team").status_code == 405


def test_openapi_declares_the_operation_without_409(client):
    op = app.openapi()["paths"]["/matches/{match_id}/team"]["get"]
    assert op["operationId"] == "getMatchTeam"
    assert set(op["responses"]) >= {"200", "401", "403", "404"}
    assert "409" not in op["responses"]
