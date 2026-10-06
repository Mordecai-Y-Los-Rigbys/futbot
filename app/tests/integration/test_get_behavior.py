import pytest

from app.models.behavior import Behavior

pytestmark = pytest.mark.integration

INVALID_IDS = [
    "abc",
    "1.5",
    "0",
    "-1",
    "2147483648",
    "99999999999999999999",
    "1_0",
    "+1",
    "9" * 5000,
]


def url(behavior_id) -> str:
    return f"/behaviors/{behavior_id}"


def add_behavior(db, user_id: int, name="mi-behavior", code="print('hola')") -> Behavior:
    behavior = Behavior(user_id=user_id, name=name, code=code)
    db.add(behavior)
    db.commit()
    db.refresh(behavior)
    return behavior


# --- 401 ----------------------------------------------------------------------


def test_no_cookie_returns_401(client):
    r = client.get(url(1))
    assert r.status_code == 401
    assert r.json() == {"code": None, "message": "Sin sesión válida."}


def test_invalid_cookie_returns_401(client):
    client.cookies.set("session_id", "no-existe")
    r = client.get(url(1))
    assert r.status_code == 401
    assert r.json()["code"] is None


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_no_cookie_with_invalid_id_returns_401(client, bad_id):
    r = client.get(url(bad_id))
    assert r.status_code == 401


def test_no_cookie_does_not_leak_behavior(client, db_session, make_user):
    make_user(1)
    behavior = add_behavior(db_session, 1, code="secreto")
    r = client.get(url(behavior.id))  # el cliente no tiene cookie
    assert r.status_code == 401
    assert "secreto" not in r.text


# --- 200 ----------------------------------------------------------------------


def test_returns_own_behavior(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, name="atacante", code="mover(1, 2)")

    r = api.get(url(behavior.id))

    assert r.status_code == 200
    assert r.json() == {"id": behavior.id, "name": "atacante", "code": "mover(1, 2)"}


def test_returns_empty_code(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, code="")

    r = api.get(url(behavior.id))

    assert r.status_code == 200
    assert r.json()["code"] == ""


def test_me_route_is_not_shadowed_by_id_route(login):
    r = login(1).get("/behaviors/me")
    assert r.status_code == 200


# --- 404 ----------------------------------------------------------------------


def test_nonexistent_id_returns_404(login):
    r = login(1).get(url(999999))
    assert r.status_code == 404
    assert r.json()["code"] is None


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_invalid_id_returns_404_not_400_or_422(login, bad_id):
    r = login(1).get(url(bad_id))
    assert r.status_code == 404
    assert r.json()["code"] is None


def test_max_valid_id_is_looked_up_normally(login):
    r = login(1).get(url(2147483647))
    assert r.status_code == 404  # válido pero inexistente, sin error de base


# --- 403 ----------------------------------------------------------------------


def test_other_users_behavior_returns_403_without_leaking(login, db_session, make_user):
    make_user(2)  # el dueño del behavior tiene que existir (FK)
    other = add_behavior(db_session, 2, name="ajeno", code="secreto")

    r = login(1).get(url(other.id))  # se loguea al final, como el usuario 1

    assert r.status_code == 403
    assert r.json()["code"] is None
    assert "ajeno" not in r.text
    assert "secreto" not in r.text


# --- solo lectura -------------------------------------------------------------


def test_get_does_not_modify_behavior(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, name="orig", code="orig-code")

    api.get(url(behavior.id))

    db_session.refresh(behavior)
    assert (behavior.name, behavior.code) == ("orig", "orig-code")
