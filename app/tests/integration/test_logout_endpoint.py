from datetime import timedelta

import pytest

from app.models.session import UserSession

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("body_kind", ["sin-body", "otra-sesion", "json-malformado"])
def test_logout_only_invalidates_cookie_session(body_kind, create_user, login_as, db_session):
    user = create_user("reader")
    api = login_as(user)
    other = login_as(user)
    sid = api.cookies["session_id"]

    if body_kind == "otra-sesion":
        response = api.post("/auth/log-out", json={"session_id": other.cookies["session_id"]})
    elif body_kind == "json-malformado":
        response = api.post(
            "/auth/log-out",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )
    else:
        response = api.post("/auth/log-out")

    assert response.status_code == 204
    assert response.content == b""
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith('session_id="";')
    assert "Max-Age=0" in set_cookie
    assert db_session.get(UserSession, sid) is None

    replay = api.get("/users/me", headers={"Cookie": f"session_id={sid}"})
    assert replay.status_code == 401
    assert replay.json()["code"] is None

    assert other.get("/users/me").status_code == 200


@pytest.mark.parametrize("state", ["sin-cookie", "inexistente", "vencida"])
def test_logout_requires_valid_session(state, client, create_user, login_as):
    if state == "inexistente":
        client.cookies.set("session_id", "sesion-inexistente")
    elif state == "vencida":
        client = login_as(create_user("expired"), expires_in=timedelta(days=-2))

    response = client.post("/auth/log-out")

    assert response.status_code == 401
    assert response.json()["code"] is None
