import pytest
from app.models.user import User
from app.models.session import UserSession  # Ajustá la ruta si está en otro archivo

def get_valid_payload():
    return {
        "username": "usuario123",
        "email": "valido@dominio.com",
        "password": "PasswordSegura1!",
        "clubName": "Club Atletico Test",
        "avatar": 1
    }

def test_register_success(client, db_session):
    payload = get_valid_payload()
    
    response = client.post("/auth/register", json=payload)
    
    # 1. Verificar estado y contrato de respuesta (201)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["username"] == payload["username"]
    assert data["clubName"] == payload["clubName"]
    assert "password" not in data
    assert "password_hash" not in data

    # 2. Verificar impacto en la base de datos (Persistencia real)
    user_in_db = db_session.query(User).filter(User.email == payload["email"]).first()
    assert user_in_db is not None
    assert user_in_db.username == payload["username"]
    
    # 3. Verificar que la contraseña no se guardó en texto plano
    assert user_in_db.password_hash != payload["password"]
    assert len(user_in_db.password_hash) > 0

    # 4. Verificar creación de sesión automática
    session_in_db = db_session.query(UserSession).filter(UserSession.user_id == user_in_db.id).first()
    assert session_in_db is not None
    
    # 5. Verificar header Set-Cookie
    assert "set-cookie" in response.headers
    assert f"session_id={session_in_db.id}" in response.headers["set-cookie"]

def test_register_duplicate_email(client, db_session):
    payload = get_valid_payload()
    
    # Primer registro exitoso
    client.post("/auth/register", json=payload)
    
    # Intento de registro duplicado
    response = client.post("/auth/register", json=payload)
    
    assert response.status_code == 409
    assert response.json() == {
        "code": None,
        "message": "El email ya está asociado a otro usuario."
    }
    
    # Verificar que no se creó un segundo usuario ni otra sesión
    assert db_session.query(User).filter(User.email == payload["email"]).count() == 1
    assert db_session.query(UserSession).count() == 1

def test_register_invalid_email_format(client, db_session):
    payload = get_valid_payload()
    invalid_emails = ["sin-arroba", "test@", "@dominio.com", "espacio @gmail.com"]
    
    for email in invalid_emails:
        payload["email"] = email
        response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 400
        errors = response.json()["errors"]
        assert any(e["field"] == "email" and e["reason"] == "invalidEmail" for e in errors)
    
    # Verificar que no impactó en DB
    assert db_session.query(User).count() == 0

def test_register_exact_limits_success(client, db_session):
    payload = {
        "username": "a" * 20,
        "email": ("c" * 245) + "@test.com",  # 255 caracteres exactos
        "password": "p" * 72,                # 72 caracteres exactos
        "clubName": "b" * 20,
        "avatar": 1
    }
    
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    assert db_session.query(User).count() == 1

def test_register_exceeds_limits_bad_request(client, db_session):
    payload = {
        "username": "a" * 21,               # > 20
        "email": ("c" * 250) + "@test.com", # Supera los 255 caracteres del límite
        "password": "p" * 73,               # > 72
        "clubName": "b" * 21,               # > 20
        "avatar": 1
    }
    
    response = client.post("/auth/register", json=payload)
    
    assert response.status_code == 400
    errors = response.json()["errors"]
    
    fields_too_long = [e["field"] for e in errors if e["reason"] == "tooLong"]
    assert "username" in fields_too_long
    assert "password" in fields_too_long
    assert "clubName" in fields_too_long
    
    # Verificamos que el email también haya fallado por longitud o por formato debido al exceso
    email_error = next((e for e in errors if e["field"] == "email"), None)
    assert email_error is not None
    assert email_error["reason"] in ["tooLong", "invalidEmail"]
    
    assert db_session.query(User).count() == 0

def test_register_missing_and_empty_fields(client, db_session):
    payload = {
        "username": "",  # Vacío
        "email": "test@test.com",
        "avatar": "  "   # Solo espacios
        # password y clubName omitidos
    }
    
    response = client.post("/auth/register", json=payload)
    
    assert response.status_code == 400
    errors = response.json()["errors"]
    
    fields_required = [e["field"] for e in errors if e["reason"] == "required"]
    assert "username" in fields_required
    assert "password" in fields_required
    assert "clubName" in fields_required
    
    assert db_session.query(User).count() == 0

def test_register_multiple_errors_simultaneously(client, db_session):
    payload = {
        "username": "a" * 25,          # tooLong
        "email": "correo-invalido",    # invalidEmail
        "password": "",                # required
        "clubName": "C",               # Válido
        "avatar": "1"                  # Válido
    }
    
    response = client.post("/auth/register", json=payload)
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "invalidFields"
    
    errors = data["errors"]
    assert {"field": "username", "reason": "tooLong"} in errors
    assert {"field": "email", "reason": "invalidEmail"} in errors
    assert {"field": "password", "reason": "required"} in errors

    assert db_session.query(User).count() == 0