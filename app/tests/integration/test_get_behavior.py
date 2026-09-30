# app/tests/.../test_get_behavior.py
import pytest

from app.models.behavior import Behavior

INVALID_IDS = ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999", "1_0", "+1", "9" * 5000]


def url(behavior_id) -> str:
    return f"/behaviors/{behavior_id}"


def add_behavior(db, user_id: int, name="mi-behavior", code="print('hola')") -> Behavior:
    behavior = Behavior(user_id=user_id, name=name, code=code)
    db.add(behavior)
    db.commit()
    db.refresh(behavior)
    return behavior


# ---------- 401 ----------

def test_no_cookie_returns_401(client):
    r = client.get(url(1))
    assert r.status_code == 401
    assert r.json() == {"code": None, "message": "Sin sesión válida."}


def test_invalid_cookie_returns_401(client):
    r = client.get(url(1), cookies={"session_id": "no-existe"})
    assert r.status_code == 401
    assert r.json()["code"] is None


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_no_cookie_with_invalid_id_returns_401(client, bad_id):
    r = client.get(url(bad_id))
    assert r.status_code == 401


def test_no_cookie_does_not_leak_behavior(client, db_session, auth_cookies):
    auth_cookies(1)
    behavior = add_behavior(db_session, 1, code="secreto")
    r = client.get(url(behavior.id))
    assert r.status_code == 401
    assert "secreto" not in r.text


# ---------- 200 ----------

def test_returns_own_behavior(client, db_session, auth_cookies):
    cookies = auth_cookies(1)
    behavior = add_behavior(db_session, 1, name="atacante", code="mover(1, 2)")

    r = client.get(url(behavior.id), cookies=cookies)

    assert r.status_code == 200
    assert r.json() == {"id": behavior.id, "name": "atacante", "code": "mover(1, 2)"}


def test_returns_empty_code(client, db_session, auth_cookies):
    cookies = auth_cookies(1)
    behavior = add_behavior(db_session, 1, code="")

    r = client.get(url(behavior.id), cookies=cookies)

    assert r.status_code == 200
    assert r.json()["code"] == ""

@pytest.mark.xfail(
    reason="GET /behaviors/me se implementa en la EPIC de listado; hasta entonces da 404",
    strict=True,
)
def test_me_route_is_not_shadowed_by_id_route(client, auth_cookies):
    cookies = auth_cookies(1)
    r = client.get("/behaviors/me", cookies=cookies)
    assert r.status_code == 200


# ---------- 404 ----------

def test_nonexistent_id_returns_404(client, auth_cookies):
    cookies = auth_cookies(1)
    r = client.get(url(999999), cookies=cookies)
    assert r.status_code == 404
    assert r.json()["code"] is None


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_invalid_id_returns_404_not_400_or_422(client, auth_cookies, bad_id):
    cookies = auth_cookies(1)
    r = client.get(url(bad_id), cookies=cookies)
    assert r.status_code == 404
    assert r.json()["code"] is None


def test_max_valid_id_is_looked_up_normally(client, auth_cookies):
    cookies = auth_cookies(1)
    r = client.get(url(2147483647), cookies=cookies)
    assert r.status_code == 404  # válido pero inexistente, sin error de base


# ---------- 403 ----------

def test_other_users_behavior_returns_403_without_leaking(client, db_session, auth_cookies):
    cookies = auth_cookies(1)
    auth_cookies(2)  # asegura que exista el usuario 2
    other = add_behavior(db_session, 2, name="ajeno", code="secreto")

    r = client.get(url(other.id), cookies=cookies)

    assert r.status_code == 403
    assert r.json()["code"] is None
    assert "ajeno" not in r.text
    assert "secreto" not in r.text


# ---------- solo lectura ----------

def test_get_does_not_modify_behavior(client, db_session, auth_cookies):
    cookies = auth_cookies(1)
    behavior = add_behavior(db_session, 1, name="orig", code="orig-code")

    client.get(url(behavior.id), cookies=cookies)

    db_session.refresh(behavior)
    assert (behavior.name, behavior.code) == ("orig", "orig-code")