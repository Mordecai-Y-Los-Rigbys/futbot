import pytest
from app.models.user import User
from app.models.session import UserSession

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
    
# --- TESTS PARA POST /auth/log-in ---

def test_login_success(client, db_session):
    """Valida el inicio de sesión exitoso, el retorno de datos sin hash y la creación de sesión."""
    # 1. Setup: Crear un usuario válido mediante el endpoint de registro
    register_payload = get_valid_payload()
    client.post("/auth/register", json=register_payload)
    
    # 2. Ejecutar el login
    login_payload = {
        "email": register_payload["email"],
        "password": register_payload["password"]
    }
    response = client.post("/auth/log-in", json=login_payload)
    
    # 3. Validar código y contrato de respuesta (200 OK)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["username"] == register_payload["username"]
    assert data["clubName"] == register_payload["clubName"]
    assert "password" not in data
    assert "password_hash" not in data

    # 4. Validar creación de sesión y cookie
    assert "set-cookie" in response.headers
    assert "session_id=" in response.headers["set-cookie"]
    
    # Extraer el ID de la cookie para verificar en DB
    cookie_str = response.headers["set-cookie"]
    session_id = cookie_str.split("session_id=")[1].split(";")[0]
    
    session_in_db = db_session.query(UserSession).filter(UserSession.id == session_id).first()
    assert session_in_db is not None

def test_login_invalid_credentials_401(client, db_session):
    """Valida que un email no registrado o contraseña incorrecta devuelvan el mismo 401."""
    # 1. Setup: Registrar un usuario
    register_payload = get_valid_payload()
    client.post("/auth/register", json=register_payload)
    
    # 2. Casos de credenciales inválidas
    invalid_cases = [
        {"email": "noexiste@dominio.com", "password": register_payload["password"]}, # Email no existe
        {"email": register_payload["email"], "password": "PasswordIncorrecta!"}      # Pass incorrecta
    ]
    
    for payload in invalid_cases:
        response = client.post("/auth/log-in", json=payload)
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] is None
        assert data["message"] == "Email o contraseña incorrectos."
        
        # Verificar que no se setea la cookie ni se crea una sesión
        assert "set-cookie" not in response.headers

def test_login_password_length_limits(client, db_session):
    """Valida que una pass de 72 chars funcione, y una de 73 chars sea rechazada con 401."""
    pass_72 = "a" * 72
    payload_72 = get_valid_payload()
    payload_72["email"] = "limite72@dominio.com"
    payload_72["password"] = pass_72
    
    # Registrar usuario con pass de 72 chars
    client.post("/auth/register", json=payload_72)
    
    # Intentar login con 73 caracteres (excede el límite, debe dar 401 genérico)
    response_73 = client.post(
        "/auth/log-in", 
        json={"email": payload_72["email"], "password": pass_72 + "a"}
    )
    assert response_73.status_code == 401
    assert response_73.json()["message"] == "Email o contraseña incorrectos."
    
    # Intentar login con los 72 caracteres exactos (debe dar 200)
    response_72 = client.post(
        "/auth/log-in", 
        json={"email": payload_72["email"], "password": pass_72}
    )
    assert response_72.status_code == 200
    assert "set-cookie" in response_72.headers

def test_login_password_with_spaces_not_trimmed(client, db_session):
    """Valida que las contraseñas con espacios no se recorten antes de verificar."""
    pass_with_spaces = "  password  "
    payload = get_valid_payload()
    payload["email"] = "espacios@dominio.com"
    payload["password"] = pass_with_spaces
    
    client.post("/auth/register", json=payload)
    
    # Login con espacios recortados (debe fallar)
    response_trimmed = client.post(
        "/auth/log-in", 
        json={"email": payload["email"], "password": "password"}
    )
    assert response_trimmed.status_code == 401
    
    # Login con espacios originales (debe pasar)
    response_exact = client.post(
        "/auth/log-in", 
        json={"email": payload["email"], "password": pass_with_spaces}
    )
    assert response_exact.status_code == 200