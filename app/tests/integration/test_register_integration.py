import json
import uuid
 
import pytest
 
from app.models.session import UserSession
from app.models.user import User
 
pytestmark = pytest.mark.integration
 
URL = "/auth/register"
LOGIN_URL = "/auth/log-in"
 
# Orden del schema RegisterUserRequest (convención 6.g y convención 9)
SCHEMA_ORDER = ["username", "email", "password", "clubName", "avatar"]
 
 
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
 
 
def payload(**overrides) -> dict:
    data = {
        "username": "messi",
        "email": unique_email(),
        "password": "Password123!",
        "clubName": "Inter Miami",
        "avatar": 3,
    }
    data.update(overrides)
    return data
 
 
def errors_of(response) -> list[dict]:
    return response.json()["errors"]
 
 
def reasons(response) -> dict:
    """{campo: reason} a partir de `errors`."""
    return {e["field"]: e["reason"] for e in errors_of(response)}
 
 
def login(client, email: str, password: str):
    return client.post(LOGIN_URL, json={"email": email, "password": password})
 
 
def assert_validation_error(response, expected: dict):
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert reasons(response) == expected
    assert "session_id" not in response.cookies
 
 
# ------------------------------------------------------------------
# 201: registro exitoso
# ------------------------------------------------------------------
 
 
def test_register_returns_201_with_only_public_user_data(client):
    response = client.post(URL, json=payload(username="messi", clubName="Inter Miami"))
 
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "username", "clubName"}
    assert isinstance(body["id"], int)
    assert body["username"] == "messi"
    assert body["clubName"] == "Inter Miami"
 
 
def test_register_never_exposes_the_password_or_its_hash(client):
    response = client.post(URL, json=payload(password="Password123!"))
 
    assert response.status_code == 201
    assert "Password123!" not in response.text
    assert "$2" not in response.text  # prefijo de un hash bcrypt
 
 
def test_register_opens_a_session_automatically(client):
    response = client.post(URL, json=payload())
 
    assert response.status_code == 201
    assert response.cookies.get("session_id")
 
 
@pytest.mark.parametrize(
    "password",
    [
        pytest.param("Password123!", id="normal"),
        pytest.param("p" * 72, id="72-ascii"),
        pytest.param("ñ" * 72, id="72-chars-multibyte"),
    ],
)
def test_registered_password_is_stored_in_a_way_login_can_verify(client, password):
    data = payload(password=password)
    assert client.post(URL, json=data).status_code == 201
 
    assert login(client, data["email"], password).status_code == 200
    assert login(client, data["email"], password + "x").status_code == 401
 
 
@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"username": "u" * 20}, id="username-20"),
        pytest.param({"clubName": "c" * 20}, id="clubName-20"),
        pytest.param({"username": "ñ" * 20, "clubName": "ñ" * 20}, id="multibyte-20"),
        pytest.param({"email": build_email(255)}, id="email-255"),
        pytest.param({"avatar": 1}, id="avatar-1"),
        pytest.param({"avatar": 5}, id="avatar-5"),
    ],
)
def test_register_persists_values_at_the_limit(client, overrides):
    # Verifica que la base soporte los máximos que el contrato permite
    assert client.post(URL, json=payload(**overrides)).status_code == 201
 
 
def test_register_ignores_unknown_fields(client):
    response = client.post(URL, json=payload(isAdmin=True, id=999999))
 
    assert response.status_code == 201
    assert response.json()["id"] != 999999
 
 
# ------------------------------------------------------------------
# 400 a través de la app real
# ------------------------------------------------------------------
 
 
def test_register_400_through_the_real_app_has_no_session(client):
    response = client.post(URL, json=payload(avatar=9))
 
    assert_validation_error(response, {"avatar": "outOfRange"})
 
 
def test_register_400_through_the_real_app_reports_every_field_in_schema_order(client):
    body = {
        "avatar": 9,
        "clubName": "c" * 21,
        "password": 123,
        "email": "no-es-un-email",
        "username": "",
    }
    response = client.post(URL, json=body)
 
    assert response.status_code == 400
    assert errors_of(response) == [
        {"field": "username", "reason": "required"},
        {"field": "email", "reason": "invalidEmail"},
        {"field": "password", "reason": "invalidType"},
        {"field": "clubName", "reason": "tooLong"},
        {"field": "avatar", "reason": "outOfRange"},
    ]
 
 
@pytest.mark.parametrize("kind", ["broken_json", "no_body", "null"])
def test_register_unreadable_body_through_the_real_app(client, kind):
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
 
 
# ------------------------------------------------------------------
# 409: email duplicado, y qué pasa cuando el registro se rechaza
# ------------------------------------------------------------------
 
 
def test_duplicate_email_returns_409_with_null_code(client):
    email = unique_email()
    assert client.post(URL, json=payload(email=email)).status_code == 201
 
    response = client.post(URL, json=payload(email=email, username="otro"))
 
    assert response.status_code == 409
    body = response.json()
    assert set(body) == {"code", "message"}
    assert body["code"] is None
    assert isinstance(body["message"], str) and body["message"]
    assert "session_id" not in response.cookies
 
 
def test_duplicate_email_does_not_overwrite_the_original_account(client):
    email = unique_email()
    assert client.post(URL, json=payload(email=email, password="Original123!")).status_code == 201
 
    second = client.post(URL, json=payload(email=email, password="Intruso456!"))
 
    assert second.status_code == 409
    assert login(client, email, "Original123!").status_code == 200
    assert login(client, email, "Intruso456!").status_code == 401
 
 
def test_validation_error_takes_precedence_over_duplicate_email(client):
    # Convención 4: 400 se evalúa antes que 409
    email = unique_email()
    assert client.post(URL, json=payload(email=email)).status_code == 201
 
    response = client.post(URL, json=payload(email=email, avatar=9))
 
    assert_validation_error(response, {"avatar": "outOfRange"})
 
 
def test_rejected_registration_creates_no_account_and_no_session(client):
    email = unique_email()
 
    rejected = client.post(URL, json=payload(email=email, avatar=9))
 
    assert_validation_error(rejected, {"avatar": "outOfRange"})
    # No hay cuenta: el login falla...
    assert login(client, email, "Password123!").status_code == 401
    # ...y el mismo email todavía se puede registrar (con una cuenta creada daría 409)
    assert client.post(URL, json=payload(email=email)).status_code == 201
 
 
# ------------------------------------------------------------------
# Lo que se verifica directo en la base (fixture db_session)
# ------------------------------------------------------------------
 
 
def test_register_stores_hashed_password_and_creates_session(client, db_session):
    """Se persiste el hash (no el texto plano) y existe la sesión de la cookie."""
    data = payload(password="securepassword", clubName="Club A")
 
    response = client.post(URL, json=data)
 
    assert response.status_code == 201
    user = db_session.query(User).filter(User.email == data["email"]).one()
    assert user.id == response.json()["id"]
    assert user.password_hash != "securepassword"
    assert user.password_hash.startswith("$2")  # prefijo de bcrypt
    assert user.username == data["username"]
    assert user.club_name == "Club A"
    assert user.avatar == data["avatar"]
 
    session = db_session.get(UserSession, response.cookies["session_id"])
    assert session is not None
    assert session.user_id == user.id
 
 
@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"email": "sin-arroba"}, id="invalid-email"),
        pytest.param({"avatar": 9}, id="avatar-out-of-range"),
        pytest.param({"username": ""}, id="empty-username"),
    ],
)
def test_register_rejected_payload_persists_nothing(client, db_session, overrides):
    data = payload(**overrides)
 
    response = client.post(URL, json=data)
 
    assert response.status_code == 400
    assert "session_id" not in response.cookies
    assert db_session.query(User).filter(User.email == data["email"]).count() == 0
 
 
def test_register_duplicate_email_persists_a_single_account_and_session(client, db_session):
    data = payload()
    assert client.post(URL, json=data).status_code == 201
 
    second = client.post(URL, json=payload(email=data["email"], username="segundouser"))
 
    assert second.status_code == 409
    assert second.json()["code"] is None
    users = db_session.query(User).filter(User.email == data["email"]).all()
    assert len(users) == 1
    assert users[0].username == data["username"]
    assert db_session.query(UserSession).filter(UserSession.user_id == users[0].id).count() == 1