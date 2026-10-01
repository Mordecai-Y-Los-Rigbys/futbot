import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_register_success_exact_limits():
    """Valida el registro exitoso aceptando valores cercanos a los límites máximos permitidos."""
    unique_email = f"user.limit.{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/auth/register",
        json={
            "username": "12345678901234567890",      # Exactamente 20 caracteres (válido)
            "email": unique_email,                   # Email único válido
            "password": "a" * 72,                    # Exactamente 72 caracteres (límite máximo válido)
            "clubName": "12345678901234567890",      # Exactamente 20 caracteres (válido)
            "avatar": 5                              # Límite superior válido (1-5)
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["username"] == "12345678901234567890"
    assert data["clubName"] == "12345678901234567890"
    assert "password" not in data
    assert "password_hash" not in data
    assert "session_id" in response.cookies


def test_register_validation_multiple_errors_and_exceeded_limits():
    """Valida múltiples campos inválidos a la vez, campos vacíos y superación de límites."""
    response = client.post(
        "/auth/register",
        json={
            "username": "123456789012345678901",    # 21 caracteres -> tooLong
            "email": "correo-invalido-sin-arroba",   # Formato inválido -> invalidEmail
            "password": "a" * 73,                    # 73 caracteres -> tooLong
            "clubName": "",                          # Vacío -> required
            "avatar": 99                             # Fuera de rango
        }
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


def test_register_email_variants_invalid_formats():
    """Valida diversos formatos de correo electrónico incorrectos que deben retornar invalidEmail."""
    invalid_emails = ["sin-arroba.com", "test@", "@dominio.com"]
    for bad_email in invalid_emails:
        response = client.post(
            "/auth/register",
            json={
                "username": "user",
                "email": bad_email,
                "password": "password123",
                "clubName": "Club",
                "avatar": 1
            }
        )
        assert response.status_code == 400
        data = response.json()
        email_errors = [err for err in data.get("errors", []) if err["field"] == "email"]
        assert len(email_errors) > 0
        assert email_errors[0]["reason"] == "invalidEmail"


def test_register_missing_fields_required():
    """Valida que la ausencia de campos obligatorios devuelva reason: required."""
    response = client.post("/auth/register", json={})
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "invalidFields"
    
    fields_with_required = {err["field"] for err in data["errors"] if err["reason"] == "required"}
    expected_fields = {"username", "email", "password", "clubName", "avatar"}
    assert expected_fields.issubset(fields_with_required)


def test_register_duplicate_email_conflict_409():
    """Valida que un email ya registrado devuelva 409 Conflict y no cree la cuenta."""
    unique_email = f"repetido.{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "username": "primeruser",
        "email": unique_email,
        "password": "securepassword",
        "clubName": "Club A",
        "avatar": 3
    }
    
    # Primer registro exitoso con un email generado al momento
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    # Segundo registro con el mismo email exacto pero diferente username
    payload["username"] = "segundouser"
    res2 = client.post("/auth/register", json=payload)
    assert res2.status_code == 409
    
    data = res2.json()
    assert data["code"] is None
    assert data["message"] is not None
    
# --- TESTS PARA POST /auth/log-in ---

def test_login_missing_and_empty_fields():
    """Valida que la ausencia de campos o campos vacíos devuelva 400 con incompleteForm."""
    payloads = [
        {},  # Faltan ambos
        {"email": "test@test.com"},  # Falta password
        {"password": "password123"},  # Falta email
        {"email": "", "password": "password123"},  # Email vacío
        {"email": "test@test.com", "password": ""},  # Password vacía
        {"email": "", "password": ""}  # Ambos vacíos
    ]
    
    for payload in payloads:
        response = client.post("/auth/log-in", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "incompleteForm"
        assert data["message"] == "Completá el email y la contraseña."

def test_login_invalid_email_format():
    """Valida el rechazo de emails mal formados en la validación inicial con invalidEmail."""
    invalid_emails = ["sin-arroba", "test@", "@dominio.com", "espacio @gmail.com"]
    
    for email in invalid_emails:
        response = client.post("/auth/log-in", json={"email": email, "password": "password123"})
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "invalidEmail"

def test_login_invalid_field_types():
    """Valida que tipos incorrectos (ej. enteros en vez de strings) devuelvan invalidFieldType."""
    payloads = [
        {"email": 12345, "password": "password123"},
        {"email": "test@test.com", "password": 12345},
        {"email": True, "password": ["array"]}
    ]
    
    for payload in payloads:
        response = client.post("/auth/log-in", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "invalidFieldType"