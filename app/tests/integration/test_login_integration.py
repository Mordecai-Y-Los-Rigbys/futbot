import json
import uuid
 
import pytest
 
pytestmark = pytest.mark.integration
 
REGISTER_URL = "/auth/register"
URL = "/auth/log-in"
 
# Orden del schema LogInRequest (convención 6.g y convención 9)
SCHEMA_ORDER = ["email", "password"]
 
UNAUTHORIZED_BODY = {"code": None, "message": "Email o contraseña incorrectos."}
 
 
# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
 
 
def unique_email() -> str:
    return f"{uuid.uuid4().hex}@test.com"
 
 
def build_email(total_length: int) -> str:
    """
    Email sintácticamente válido, único y de exactamente `total_length`
    caracteres: local de 64, labels de dominio de hasta 63 y TLD "com".
    """
    local = uuid.uuid4().hex + "a" * 32  # 64 caracteres
    remaining = total_length - len(local) - 1 - len("com")  # 1 = la "@"
    labels: list[str] = []
    while remaining > 0:
        size = min(63, remaining - 1)  # -1 por el punto que sigue a cada label
        labels.append("b" * size)
        remaining -= size + 1
    email = f"{local}@{'.'.join(labels)}.com"
    assert len(email) == total_length
    return email
 
 
def credentials(**overrides) -> dict:
    data = {"email": unique_email(), "password": "Password123!"}
    data.update(overrides)
    return data
 
 
def register_user(client, email: str | None = None, password: str = "Password123!", **extra) -> dict:
    """Registra un usuario por la API y devuelve sus credenciales y la respuesta."""
    data = {
        "username": "messi",
        "email": email or unique_email(),
        "password": password,
        "clubName": "Inter Miami",
        "avatar": 3,
    }
    data.update(extra)
    response = client.post(REGISTER_URL, json=data)
    assert response.status_code == 201, response.text
    return {"email": data["email"], "password": data["password"], "registered": response.json()}
 
 
def errors_of(response) -> list[dict]:
    return response.json()["errors"]
 
 
# ------------------------------------------------------------------
# 200: inicio de sesión exitoso
# ------------------------------------------------------------------
 
 
def test_login_returns_200_with_only_public_user_data(client):
    user = register_user(client, username="messi", clubName="Inter Miami")
 
    response = client.post(URL, json={"email": user["email"], "password": user["password"]})
 
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "username", "clubName"}
    assert body == user["registered"]
 
 
def test_login_sets_the_session_cookie(client):
    user = register_user(client)
 
    response = client.post(URL, json={"email": user["email"], "password": user["password"]})
 
    assert response.status_code == 200
    assert response.cookies.get("session_id")
 
 
def test_login_never_exposes_the_password_or_its_hash(client):
    user = register_user(client, password="Password123!")
 
    response = client.post(URL, json={"email": user["email"], "password": "Password123!"})
 
    assert response.status_code == 200
    assert "Password123!" not in response.text
    assert "$2" not in response.text  # prefijo de un hash bcrypt
 
 
@pytest.mark.parametrize(
    "password",
    [
        pytest.param("p" * 72, id="72-ascii"),
        pytest.param("ñ" * 72, id="72-chars-multibyte"),
    ],
)
def test_login_accepts_a_password_of_exactly_72_characters(client, password):
    user = register_user(client, password=password)
 
    response = client.post(URL, json={"email": user["email"], "password": password})
 
    assert response.status_code == 200
 
 
def test_user_registered_with_a_255_character_email_can_log_in(client):
    user = register_user(client, email=build_email(255))
 
    response = client.post(URL, json={"email": user["email"], "password": user["password"]})
 
    assert response.status_code == 200
    assert response.json() == user["registered"]
 
 
def test_login_does_not_trim_the_password(client):
    # El ticket: "no se modifica ni recorta la contraseña antes de verificarla"
    user = register_user(client, password="  Clave123  ")
 
    trimmed = client.post(URL, json={"email": user["email"], "password": "Clave123"})
    exact = client.post(URL, json={"email": user["email"], "password": "  Clave123  "})
 
    assert trimmed.status_code == 401
    assert exact.status_code == 200
 
 
def test_each_user_logs_in_with_their_own_data(client):
    first = register_user(client, username="primero", password="ClaveDelPrimero1")
    second = register_user(client, username="segundo", password="ClaveDelSegundo2")
 
    response = client.post(URL, json={"email": second["email"], "password": second["password"]})
 
    assert response.status_code == 200
    assert response.json()["username"] == "segundo"
    assert response.json()["id"] != first["registered"]["id"]
    # La contraseña de un usuario no abre la cuenta del otro
    cross = client.post(URL, json={"email": second["email"], "password": first["password"]})
    assert cross.status_code == 401
 
 
# ------------------------------------------------------------------
# 401: mismo cuerpo en los tres casos
# ------------------------------------------------------------------
 
 
def test_unknown_email_returns_401(client):
    response = client.post(URL, json=credentials())
 
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
 
 
def test_wrong_password_returns_401(client):
    user = register_user(client)
 
    response = client.post(URL, json={"email": user["email"], "password": "Incorrecta123!"})
 
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
 
 
@pytest.mark.parametrize("length", [73, 300])
def test_password_longer_than_72_characters_returns_401(client, length):
    # Llega al servicio (no es 400) y responde igual que cualquier credencial inválida
    user = register_user(client, password="p" * 72)
 
    response = client.post(URL, json={"email": user["email"], "password": "p" * length})
 
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
 
 
def test_the_three_401_cases_are_indistinguishable(client):
    user = register_user(client, password="p" * 72)
 
    unknown_email = client.post(URL, json=credentials())
    wrong_password = client.post(URL, json={"email": user["email"], "password": "x" * 10})
    too_long = client.post(URL, json={"email": user["email"], "password": "p" * 73})
 
    assert unknown_email.status_code == wrong_password.status_code == too_long.status_code == 401
    assert unknown_email.json() == wrong_password.json() == too_long.json() == UNAUTHORIZED_BODY
 
 
@pytest.mark.parametrize("case", ["unknown_email", "wrong_password", "too_long_password"])
def test_a_rejected_login_sets_no_session_cookie(client, case):
    user = register_user(client, password="p" * 72)
    body = {
        "unknown_email": credentials(),
        "wrong_password": {"email": user["email"], "password": "x" * 10},
        "too_long_password": {"email": user["email"], "password": "p" * 73},
    }[case]
 
    response = client.post(URL, json=body)
 
    assert response.status_code == 401
    assert "session_id" not in response.cookies
 
 
# ------------------------------------------------------------------
# 400 a través de la app real
# ------------------------------------------------------------------
 
 
def test_login_400_through_the_real_app_has_no_session(client):
    response = client.post(URL, json={"email": "no-es-un-email", "password": ""})
 
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert errors_of(response) == [
        {"field": "email", "reason": "invalidEmail"},
        {"field": "password", "reason": "required"},
    ]
    assert "session_id" not in response.cookies
 
 
@pytest.mark.parametrize("kind", ["broken_json", "no_body", "null"])
def test_login_unreadable_body_through_the_real_app(client, kind):
    headers = {"Content-Type": "application/json"}
    if kind == "broken_json":
        response = client.post(URL, content="{esto no es json", headers=headers)
    elif kind == "no_body":
        response = client.post(URL)
    else:
        response = client.post(URL, content=json.dumps(None), headers=headers)
 
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert errors_of(response) == [{"field": f, "reason": "required"} for f in SCHEMA_ORDER]
    assert "session_id" not in response.cookies
 
 
def test_validation_error_takes_precedence_over_unauthorized(client):
    # Convención 4: el 400 se evalúa antes que el 401 de credenciales.
    # El email no está registrado, pero el password vacío se rechaza primero.
    response = client.post(URL, json=credentials(password=""))
 
    assert response.status_code == 400
    assert errors_of(response) == [{"field": "password", "reason": "required"}]
    assert "session_id" not in response.cookies