import pytest

from app.models.session import UserSession
from app.models.user import User

pytestmark = pytest.mark.integration


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

def test_openapi_documents_the_auth_error_schemas():
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    assert "LogInBadRequest" in schemas
    assert "RegisterUserBadRequest" in schemas


# ==============================================================================
# PRUEBAS DE INTEGRACIÓN: POST /auth/register
# ==============================================================================

def test_register_success_exact_limits(client):
    """Valida el registro exitoso aceptando valores cercanos a los límites máximos permitidos."""
    response = client.post(
        "/auth/register",
        json={
            "username": "12345678901234567890",
            "email": "user.limit@example.com",
            "password": "a" * 72,
            "clubName": "12345678901234567890",
            "avatar": 5,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["username"] == "12345678901234567890"
    assert data["clubName"] == "12345678901234567890"
    assert "password" not in data
    assert "password_hash" not in data
    assert "session_id" in response.cookies


def test_register_stores_hashed_password_and_creates_session(client, db_session):
    """Valida que se persista el hash (no el texto plano) y que exista la sesión de la cookie."""
    response = client.post("/auth/register", json=register_payload())
    assert response.status_code == 201

    user = db_session.query(User).filter(User.email == "user@example.com").one()
    assert user.password_hash != "securepassword"
    assert user.password_hash.startswith("$2")  # prefijo de bcrypt
    assert user.club_name == "Club A"

    session = db_session.get(UserSession, response.cookies["session_id"])
    assert session is not None
    assert session.user_id == user.id


def test_register_validation_multiple_errors_and_exceeded_limits(client):
    """Valida múltiples campos inválidos a la vez, campos vacíos y superación de límites."""
    response = client.post(
        "/auth/register",
        json={
            "username": "123456789012345678901",
            "email": "correo-invalido-sin-arroba",
            "password": "a" * 73,
            "clubName": "",
            "avatar": 99,
        },
    )
    assert response.status_code == 400
    data = response.json()

    assert data["code"] == "invalidFields"
    assert "errors" in data

    errors = {err["field"]: err["reason"] for err in data["errors"]}
    assert errors.get("username") == "tooLong"
    assert errors.get("email") == "invalidEmail"
    assert errors.get("password") == "tooLong"
    assert errors.get("clubName") == "required"
    assert "avatar" in errors


def test_register_invalid_payload_persists_nothing(client, db_session):
    response = client.post("/auth/register", json=register_payload(email="sin-arroba"))

    assert response.status_code == 400
    assert db_session.query(User).count() == 0


def test_register_email_variants_invalid_formats(client):
    """Valida diversos formatos de correo electrónico incorrectos que deben retornar invalidEmail."""
    invalid_emails = ["sin-arroba.com", "test@", "@dominio.com"]
    for bad_email in invalid_emails:
        response = client.post(
            "/auth/register",
            json=register_payload(email=bad_email, username="user", password="password123"),
        )
        assert response.status_code == 400
        data = response.json()
        email_errors = [err for err in data.get("errors", []) if err["field"] == "email"]
        assert len(email_errors) > 0
        assert email_errors[0]["reason"] == "invalidEmail"


def test_register_missing_fields_required(client):
    """Valida que la ausencia de campos obligatorios devuelva reason: required."""
    response = client.post("/auth/register", json={})
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "invalidFields"

    fields_with_required = {err["field"] for err in data["errors"] if err["reason"] == "required"}
    expected_fields = {"username", "email", "password", "clubName", "avatar"}
    assert expected_fields.issubset(fields_with_required)


def test_register_duplicate_email_conflict_409(client, db_session):
    """Valida que un email ya registrado devuelva 409 Conflict y no cree la cuenta."""
    payload = register_payload()

    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    payload["username"] = "segundouser"
    res2 = client.post("/auth/register", json=payload)
    assert res2.status_code == 409

    data = res2.json()
    assert data["code"] is None
    assert data["message"] is not None
    assert db_session.query(User).count() == 1


# ==============================================================================
# PRUEBAS DE INTEGRACIÓN: POST /auth/log-in
# ==============================================================================

def test_login_after_register_succeeds(client):
    client.post("/auth/register", json=register_payload())
    client.cookies.clear()

    response = client.post(
        "/auth/log-in",
        json={"email": "user@example.com", "password": "securepassword"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "primeruser"
    assert "session_id" in response.cookies


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json=register_payload())

    response = client.post(
        "/auth/log-in",
        json={"email": "user@example.com", "password": "incorrecta"},
    )

    assert response.status_code == 401
    assert response.json()["code"] is None


def test_login_missing_and_empty_fields(client):
    """Valida que la ausencia de campos o campos vacíos devuelva 400 con incompleteForm."""
    payloads = [
        {},
        {"email": "test@test.com"},
        {"password": "password123"},
        {"email": "", "password": "password123"},
        {"email": "test@test.com", "password": ""},
        {"email": "", "password": ""},
    ]

    for payload in payloads:
        response = client.post("/auth/log-in", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "incompleteForm"
        assert data["message"] == "Completá el email y la contraseña."


def test_login_invalid_email_format(client):
    """Valida el rechazo de emails mal formados en la validación inicial con invalidEmail."""
    invalid_emails = ["sin-arroba", "test@", "@dominio.com", "espacio @gmail.com"]

    for email in invalid_emails:
        response = client.post("/auth/log-in", json={"email": email, "password": "password123"})
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "invalidEmail"


def test_login_invalid_field_types(client):
    """Valida que tipos incorrectos (ej. enteros en vez de strings) devuelvan invalidFieldType."""
    payloads = [
        {"email": 12345, "password": "password123"},
        {"email": "test@test.com", "password": 12345},
        {"email": True, "password": ["array"]},
    ]

    for payload in payloads:
        response = client.post("/auth/log-in", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "invalidFieldType"