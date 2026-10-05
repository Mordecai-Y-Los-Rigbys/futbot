from datetime import timedelta

import pytest

pytestmark = pytest.mark.integration

UNAUTHORIZED = {"code": None, "message": "Sin sesión válida."}


def register_payload(**over):
    payload = {
        "username": "primeruser",
        "email": "user@example.com",
        "password": "securepassword",
        "clubName": "Club A",
        "avatar": 3,
    }
    payload.update(over)
    return payload


def test_openapi_documents_users_me():
    from app.main import app

    operation = app.openapi()["paths"]["/users/me"]["get"]
    assert "401" in operation["responses"]
    assert "Users" in operation["tags"]


# ---------- Éxito ----------

def test_me_matches_database_row(create_user, login_as, db_session):
    user = create_user("mgonzalez", club_name="Boca Juniors")
    api = login_as(user)

    response = api.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "username": "mgonzalez",
        "clubName": "Boca Juniors",
    }


def test_me_does_not_expose_private_fields(create_user, login_as):
    api = login_as(create_user("mgonzalez"))

    data = api.get("/users/me").json()

    assert set(data) == {"id", "username", "clubName"}


def test_me_returns_each_users_own_data(create_user, login_as):
    ana = create_user("ana", club_name="Club Ana")
    beto = create_user("beto", club_name="Club Beto")

    assert login_as(ana).get("/users/me").json()["username"] == "ana"
    assert login_as(beto).get("/users/me").json()["clubName"] == "Club Beto"


# ---------- Flujo completo con cookie real ----------

def test_register_then_me(client):
    registered = client.post("/auth/register", json=register_payload()).json()

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == registered
    assert response.json()["clubName"] == "Club A"


def test_login_then_me(client):
    client.post("/auth/register", json=register_payload())
    client.cookies.clear()

    login = client.post(
        "/auth/log-in",
        json={"email": "user@example.com", "password": "securepassword"},
    )
    assert login.status_code == 200

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == login.json()
    assert response.json()["username"] == "primeruser"


# ---------- Autenticación ----------

def test_me_without_cookie_returns_401(client):
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_me_with_tampered_cookie_returns_401(client):
    client.cookies.set("session_id", "cookie-que-no-existe")

    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_me_with_expired_session_returns_401(create_user, login_as):
    api = login_as(create_user("mgonzalez"), expires_in=timedelta(days=-1))

    response = api.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_me_with_session_of_deleted_user_returns_401(create_user, login_as, db_session):
    """Sesión válida cuyo usuario ya no existe. Si la tabla de sesiones tiene FK
    a users sin ON DELETE CASCADE, el delete falla: en ese caso este caso no se
    puede armar en integración y queda cubierto por el unit test."""
    user = create_user("mgonzalez")
    api = login_as(user)

    db_session.delete(user)
    db_session.commit()

    response = api.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    

def test_openapi_users_me_matches_contract():
    from app.main import app

    spec = app.openapi()
    assert spec["paths"]["/users/me"]["get"]["operationId"] == "getCurrentUser"
    assert "User" in spec["components"]["schemas"]
    assert "UserResponse" not in spec["components"]["schemas"]