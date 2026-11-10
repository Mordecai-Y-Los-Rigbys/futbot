from types import SimpleNamespace
from http.cookies import SimpleCookie
from unittest.mock import create_autospec

from app.api import ws_league_deps
from app.api.ws_league_deps import get_league_channel_managers
from app.main import app
from app.api.auth import user_logout
from app.api.deps import CurrentSession
from app.services.session_service import SessionService


def test_logout_deletes_current_session_and_expires_cookie():
    service = create_autospec(SessionService, instance=True)
    session = CurrentSession(id="sesion-actual", user_id=7)

    response = user_logout(session=session, service=service, channels=[])

    service.delete.assert_called_once_with("sesion-actual")
    assert response.status_code == 204
    assert response.body == b""

    cookie = SimpleCookie(response.headers["set-cookie"])["session_id"]
    assert cookie.value == ""
    assert cookie["max-age"] == "0"
    assert cookie["httponly"]
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"


def test_logout_by_http_returns_204_and_deletes_session(auth_api, fake_sessions):
    res = auth_api.post("/auth/log-out")

    assert res.status_code == 204
    assert res.content == b""
    assert fake_sessions.deleted == ["valid-session"]


def test_logout_without_cookie_returns_401(api, fake_sessions):
    res = api.post("/auth/log-out")

    assert res.status_code == 401
    assert res.json()["code"] is None
    assert fake_sessions.deleted == []


def test_logout_with_unknown_session_returns_401(api, fake_sessions):
    api.cookies.set("session_id", "no-existe")

    res = api.post("/auth/log-out")

    assert res.status_code == 401
    assert res.json()["code"] is None
    assert fake_sessions.deleted == []


def test_logout_with_expired_session_returns_401(api, fake_sessions):
    # SessionService.get_user_id devuelve None para una sesión vencida
    fake_sessions.sessions["vencida"] = 7
    fake_sessions.get_user_id = lambda sid: None if sid == "vencida" else 7
    api.cookies.set("session_id", "vencida")

    res = api.post("/auth/log-out")

    assert res.status_code == 401
    assert res.json()["code"] is None
    assert fake_sessions.deleted == []


def test_same_cookie_after_logout_returns_401(auth_api):
    assert auth_api.post("/auth/log-out").status_code == 204

    # el TestClient borra la cookie expirada, así que se reenvía a mano
    auth_api.cookies.set("session_id", "valid-session")
    res = auth_api.post("/auth/log-out")

    assert res.status_code == 401
    assert res.json()["code"] is None


def test_logout_ignores_body(auth_api, fake_sessions):
    res = auth_api.post(
        "/auth/log-out",
        content=b"{no es json",
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 204
    assert fake_sessions.deleted == ["valid-session"]


def test_logout_closes_the_league_channels_after_deleting_the_session():
    calls = []
    service = create_autospec(SessionService, instance=True)
    service.delete.side_effect = lambda sid: calls.append(("delete", sid))
    channels = [
        SimpleNamespace(session_ended=lambda sid, name=name: calls.append((name, sid)))
        for name in ("participants", "fixture")
    ]

    user_logout(session=CurrentSession(id="s1", user_id=7), service=service, channels=channels)

    assert calls == [("delete", "s1"), ("participants", "s1"), ("fixture", "s1")]


def test_a_rejected_logout_does_not_touch_the_league_channels(api):
    ended = []
    app.dependency_overrides[get_league_channel_managers] = lambda: [
        SimpleNamespace(session_ended=ended.append)
    ]
    try:
        assert api.post("/auth/log-out").status_code == 401
    finally:
        app.dependency_overrides.pop(get_league_channel_managers, None)
    assert ended == []


def test_the_league_channels_are_participants_fixture_ranking_and_next_match():
    assert ws_league_deps.get_league_channel_managers() == [
        ws_league_deps.get_league_participants_manager(),
        ws_league_deps.get_league_fixture_manager(),
        ws_league_deps.get_league_ranking_manager(),
        ws_league_deps.get_league_next_match_manager(),
    ]
