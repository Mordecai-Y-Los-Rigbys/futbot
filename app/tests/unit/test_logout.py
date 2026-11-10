from http.cookies import SimpleCookie
from unittest.mock import create_autospec

from app.api.auth import user_logout
from app.api.deps import CurrentSession
from app.services.session_service import SessionService


def test_logout_deletes_current_session_and_expires_cookie():
    service = create_autospec(SessionService, instance=True)
    session = CurrentSession(id="sesion-actual", user_id=7)

    response = user_logout(session=session, service=service)

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
