import json
import uuid

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.errors import validation_exception_handler
from app.schemas.auth import RegisterUserRequest

URL = "/auth/register"
LOGIN_URL = "/auth/log-in"

# Orden del schema RegisterUserRequest (convención 6.g y convención 9)
SCHEMA_ORDER = ["username", "email", "password", "clubName", "avatar"]
STRING_FIELDS = ["username", "email", "password", "clubName"]

UNREADABLE_KINDS = ["broken_json", "no_body", "null", "array", "string", "number"]


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


def without(data: dict, field: str) -> dict:
    return {k: v for k, v in data.items() if k != field}


def errors_of(response) -> list[dict]:
    return response.json()["errors"]


def reasons(response) -> dict:
    """{campo: reason} a partir de `errors`."""
    return {e["field"]: e["reason"] for e in errors_of(response)}


def assert_validation_error(response, expected: dict):
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert reasons(response) == expected
    assert "session_id" not in response.cookies


def assert_all_required(response):
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert errors_of(response) == [{"field": f, "reason": "required"} for f in SCHEMA_ORDER]


def post_unreadable(test_client, kind: str, url: str = URL):
    """Body ilegible: JSON roto, sin body o algo que no es un objeto."""
    headers = {"Content-Type": "application/json"}
    if kind == "broken_json":
        return test_client.post(url, content="{esto no es json", headers=headers)
    if kind == "no_body":
        return test_client.post(url)
    if kind == "null":
        return test_client.post(url, content="null", headers=headers)
    values = {"array": [], "string": "texto", "number": 42}
    return test_client.post(url, content=json.dumps(values[kind]), headers=headers)


def login(client, email: str, password: str):
    return client.post(LOGIN_URL, json={"email": email, "password": password})


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def validation_client():
    """App mínima: solo validación del request, sin servicios ni base."""
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.post(URL)
    def register(body: RegisterUserRequest):
        return {"ok": True}

    return TestClient(app)


@pytest.fixture(scope="module")
def prefixed_validation_client():
    """Mismo handler, pero con el router montado bajo un prefijo."""
    router = APIRouter(prefix="/api")

    @router.post(URL)
    def register(body: RegisterUserRequest):
        return {"ok": True}

    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    return TestClient(app)


# ==================================================================
# A) VALIDACIÓN (sin base de datos)
# ==================================================================

# -- Camino feliz y límites --------------------------------------


def test_valid_body_passes_validation(validation_client):
    assert validation_client.post(URL, json=payload()).status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"username": "u" * 20}, id="username-20"),
        pytest.param({"clubName": "c" * 20}, id="clubName-20"),
        pytest.param({"username": "ñ" * 20, "clubName": "ñ" * 20}, id="multibyte-20"),
        pytest.param({"password": "p" * 72}, id="password-72"),
        pytest.param({"password": "ñ" * 72}, id="password-72-multibyte"),
        pytest.param({"email": build_email(255)}, id="email-255"),
        pytest.param({"avatar": 1}, id="avatar-1"),
        pytest.param({"avatar": 2}, id="avatar-2"),
        pytest.param({"avatar": 3}, id="avatar-3"),
        pytest.param({"avatar": 4}, id="avatar-4"),
        pytest.param({"avatar": 5}, id="avatar-5"),
    ],
)
def test_values_at_the_limit_are_accepted(validation_client, overrides):
    assert validation_client.post(URL, json=payload(**overrides)).status_code == 200


def test_unknown_fields_are_ignored(validation_client):
    # Convención 7: lo que no está en el schema se ignora sin error
    assert validation_client.post(URL, json=payload(isAdmin=True, id=999)).status_code == 200


@pytest.mark.parametrize(
    "field, value",
    [
        pytest.param("username", "u" * 21, id="username-21"),
        pytest.param("clubName", "c" * 21, id="clubName-21"),
        pytest.param("password", "p" * 73, id="password-73"),
        pytest.param("password", "ñ" * 73, id="password-73-multibyte"),
    ],
)
def test_one_character_over_the_limit_is_too_long(validation_client, field, value):
    response = validation_client.post(URL, json=payload(**{field: value}))

    assert_validation_error(response, {field: "tooLong"})


@pytest.mark.parametrize(
    "email",
    [
        pytest.param(build_email(256), id="valido-de-256"),
        pytest.param("a" * 256, id="sin-formato-de-256"),
        pytest.param("a" * 290 + "@test.com", id="299-caracteres"),
    ],
)
def test_email_over_255_characters_is_too_long(validation_client, email):
    # tooLong gana sobre invalidEmail (convención 6.e)
    response = validation_client.post(URL, json=payload(email=email))

    assert_validation_error(response, {"email": "tooLong"})


# -- Un reason por campo, con la precedencia del contrato ---------


@pytest.mark.parametrize("field", SCHEMA_ORDER)
def test_missing_field_is_required(validation_client, field):
    response = validation_client.post(URL, json=without(payload(), field))

    assert_validation_error(response, {field: "required"})


@pytest.mark.parametrize("field", STRING_FIELDS)
def test_empty_string_is_required(validation_client, field):
    response = validation_client.post(URL, json=payload(**{field: ""}))

    assert_validation_error(response, {field: "required"})


@pytest.mark.parametrize("field", STRING_FIELDS)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param(123, id="number"),
        pytest.param(True, id="bool"),
        pytest.param([], id="array"),
        pytest.param({}, id="object"),
    ],
)
def test_string_field_with_wrong_type_is_invalid_type(validation_client, field, value):
    response = validation_client.post(URL, json=payload(**{field: value}))

    assert_validation_error(response, {field: "invalidType"})


@pytest.mark.parametrize(
    "email",
    [
        pytest.param("no-es-un-email", id="sin-arroba"),
        pytest.param("a@b", id="sin-punto-en-dominio"),
        pytest.param("a@b..com", id="punto-doble"),
        pytest.param("@b.com", id="sin-local"),
        pytest.param("con espacio@b.com", id="espacio"),
        pytest.param("a" * 65 + "@b.com", id="local-de-65"),
        pytest.param("a" * 251 + "@b.c", id="local-de-251"),
        pytest.param("a@" + "b" * 64 + ".com", id="label-de-64"),
    ],
)
def test_badly_formatted_email_is_invalid_email(validation_client, email):
    response = validation_client.post(URL, json=payload(email=email))

    assert_validation_error(response, {"email": "invalidEmail"})


@pytest.mark.parametrize(
    "avatar",
    [
        pytest.param("a", id="string"),
        pytest.param("3", id="string-numerico"),
        pytest.param("", id="string-vacio"),
        pytest.param(1.5, id="decimal"),
        pytest.param(3.0, id="decimal-entero"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param(None, id="null"),
        pytest.param([], id="array"),
    ],
)
def test_avatar_that_is_not_an_integer_is_invalid_type(validation_client, avatar):
    response = validation_client.post(URL, json=payload(avatar=avatar))

    assert_validation_error(response, {"avatar": "invalidType"})


@pytest.mark.parametrize("avatar", [0, 6, -1, 100, 2147483648])
def test_integer_avatar_outside_1_to_5_is_out_of_range(validation_client, avatar):
    response = validation_client.post(URL, json=payload(avatar=avatar))

    assert_validation_error(response, {"avatar": "outOfRange"})


# -- Formato del 400 ---------------------------------------------


def test_400_has_the_contract_shape(validation_client):
    response = validation_client.post(URL, json=payload(username=""))

    assert response.status_code == 400
    body = response.json()
    assert set(body) == {"code", "message", "errors"}
    assert body["code"] == "invalidFields"
    assert isinstance(body["message"], str) and body["message"]
    assert body["errors"] == [{"field": "username", "reason": "required"}]


def test_every_failing_field_is_reported_once_in_schema_order(validation_client):
    # El body trae los campos en orden inverso: el orden de `errors` es el del schema
    body = {
        "avatar": 9,
        "clubName": "c" * 21,
        "password": 123,
        "email": "no-es-un-email",
        "username": "",
    }
    response = validation_client.post(URL, json=body)

    assert response.status_code == 400
    assert errors_of(response) == [
        {"field": "username", "reason": "required"},
        {"field": "email", "reason": "invalidEmail"},
        {"field": "password", "reason": "invalidType"},
        {"field": "clubName", "reason": "tooLong"},
        {"field": "avatar", "reason": "outOfRange"},
    ]


def test_all_fields_missing_reports_all_required_in_schema_order(validation_client):
    assert_all_required(validation_client.post(URL, json={}))


# -- Body ilegible (convención 9) --------------------------------


@pytest.mark.parametrize("kind", UNREADABLE_KINDS)
def test_unreadable_body_reports_all_five_fields_required(validation_client, kind):
    assert_all_required(post_unreadable(validation_client, kind))


def test_handler_applies_under_a_router_prefix(prefixed_validation_client):
    response = prefixed_validation_client.post("/api" + URL, json={})

    assert_all_required(response)


# ==================================================================
# B) CONTRATO END-TO-END (app real con base de datos)
# ==================================================================

# -- 201: registro exitoso ---------------------------------------


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


# -- 400 a través de la app real ---------------------------------


def test_register_400_through_the_real_app_has_no_session(client):
    response = client.post(URL, json=payload(avatar=9))

    assert_validation_error(response, {"avatar": "outOfRange"})


@pytest.mark.parametrize("kind", ["broken_json", "no_body", "null"])
def test_register_unreadable_body_through_the_real_app(client, kind):
    assert_all_required(post_unreadable(client, kind))


# -- 409: email duplicado y qué pasa cuando el registro se rechaza -


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