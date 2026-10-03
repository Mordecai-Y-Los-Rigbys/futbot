import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.errors import REGISTER_FIELDS, validation_exception_handler
from app.schemas.auth import LogInRequest, RegisterUserRequest

BASE = dict(
    username="messi",
    email="messi@test.com",
    password="Password123!",
    clubName="Inter Miami",
    avatar=3,
)


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.post("/auth/register")
    def register(body: RegisterUserRequest):
        return {"ok": True}

    @app.post("/auth/log-in")
    def login(body: LogInRequest):
        return {"ok": True}

    return TestClient(app)


def body(**over):
    data = dict(BASE)
    data.update(over)
    return data


def reasons(response) -> dict:
    """{campo: reason} a partir de la lista `errors` de la respuesta."""
    return {e["field"]: e["reason"] for e in response.json()["errors"]}


def assert_all_required(response):
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert reasons(response) == {f: "required" for f in REGISTER_FIELDS}


# ==============================================================================
# Register: sanity check
# ==============================================================================

def test_register_valid_body_passes_validation(client):
    assert client.post("/auth/register", json=body()).status_code == 200


# ==============================================================================
# Register: body ilegible (antes daba 500)
# ==============================================================================

def test_register_broken_json_reports_all_fields_required(client):
    response = client.post(
        "/auth/register",
        content="{esto no es json",
        headers={"Content-Type": "application/json"},
    )
    assert_all_required(response)


def test_register_without_body_reports_all_fields_required(client):
    assert_all_required(client.post("/auth/register"))


def test_register_array_body_reports_all_fields_required(client):
    assert_all_required(client.post("/auth/register", json=[]))


# ==============================================================================
# Register: invalidType
# ==============================================================================

def test_register_username_not_a_string_is_invalid_type(client):
    response = client.post("/auth/register", json=body(username=123))

    assert response.status_code == 400
    assert reasons(response) == {"username": "invalidType"}


@pytest.mark.parametrize("avatar", ["a", "3", 0, 6, -1, 1.5, 3.0, True, False, None])
def test_register_bad_avatar_is_invalid_type(client, avatar):
    response = client.post("/auth/register", json=body(avatar=avatar))

    assert response.status_code == 400
    assert reasons(response) == {"avatar": "invalidType"}


@pytest.mark.parametrize("avatar", [1, 2, 3, 4, 5])
def test_register_valid_avatars_are_accepted(client, avatar):
    assert client.post("/auth/register", json=body(avatar=avatar)).status_code == 200


# ==============================================================================
# Register: email (required / tooLong / invalidEmail)
# ==============================================================================

def test_register_email_of_300_chars_is_too_long(client):
    long_email = "a" * 290 + "@test.com"  # 299 caracteres
    response = client.post("/auth/register", json=body(email=long_email))

    assert response.status_code == 400
    assert reasons(response) == {"email": "tooLong"}


def test_register_empty_email_is_required(client):
    response = client.post("/auth/register", json=body(email=""))

    assert response.status_code == 400
    assert reasons(response) == {"email": "required"}


def test_register_invalid_email_format_is_invalid_email(client):
    response = client.post("/auth/register", json=body(email="no-es-un-email"))

    assert response.status_code == 400
    assert reasons(response) == {"email": "invalidEmail"}


def test_register_email_255_chars_is_invalid_email(client):
    email = "a" * 251 + "@b.c"  # 255 caracteres: no supera el máximo, pero el formato es inválido
    assert len(email) == 255
    response = client.post("/auth/register", json=body(email=email))

    assert response.status_code == 400
    assert reasons(response) == {"email": "invalidEmail"}


def test_register_email_256_chars_is_too_long(client):
    email = "a" * 252 + "@b.c"  # 256 caracteres
    assert len(email) == 256
    response = client.post("/auth/register", json=body(email=email))

    assert response.status_code == 400
    assert reasons(response) == {"email": "tooLong"}


# ==============================================================================
# Register: tooLong / required en el resto de los campos
# ==============================================================================

@pytest.mark.parametrize(
    "field, value",
    [
        ("username", "u" * 21),
        ("clubName", "c" * 21),
        ("password", "p" * 73),
    ],
)
def test_register_fields_over_the_limit_are_too_long(client, field, value):
    response = client.post("/auth/register", json=body(**{field: value}))

    assert response.status_code == 400
    assert reasons(response) == {field: "tooLong"}


@pytest.mark.parametrize("field", REGISTER_FIELDS)
def test_register_missing_field_is_required(client, field):
    data = body()
    del data[field]
    response = client.post("/auth/register", json=data)

    assert response.status_code == 400
    assert reasons(response) == {field: "required"}


@pytest.mark.parametrize("field", ["username", "password", "clubName"])
def test_register_empty_string_is_required(client, field):
    response = client.post("/auth/register", json=body(**{field: ""}))

    assert response.status_code == 400
    assert reasons(response) == {field: "required"}


# ==============================================================================
# Register: contraseña de 72 caracteres multibyte
# ==============================================================================

def test_register_accepts_72_multibyte_char_password(client):
    assert client.post("/auth/register", json=body(password="ñ" * 72)).status_code == 200


# ==============================================================================
# Register: varios campos mal a la vez (no se corta en el primero)
# ==============================================================================

def test_register_multiple_failures_are_all_reported(client):
    response = client.post(
        "/auth/register",
        json=body(
            username="",             # required
            email="no-es-un-email",  # invalidEmail
            password="p" * 73,       # tooLong
            avatar="3",              # invalidType (strict)
        ),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert reasons(response) == {
        "username": "required",
        "email": "invalidEmail",
        "password": "tooLong",
        "avatar": "invalidType",
    }


@pytest.mark.parametrize("payload", [None, [], "texto", 42])
def test_register_errors_list_is_never_empty(client, payload):
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert len(response.json()["errors"]) >= 1


# ==============================================================================
# Login: validación (schema + handler)
# ==============================================================================

def test_login_schema_accepts_300_char_password(client):
    # Ya no hay max_length en el schema: el service responde 401 sobre 72
    response = client.post(
        "/auth/log-in", json={"email": "messi@test.com", "password": "a" * 300}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload, code",
    [
        ({"email": "messi@test.com"}, "incompleteForm"),
        ({"email": "messi@test.com", "password": ""}, "incompleteForm"),
        ({"email": "messi@test.com", "password": 123}, "invalidFieldType"),
        ({"email": "no-es-un-email", "password": "x"}, "invalidEmail"),
    ],
)
def test_login_validation_codes(client, payload, code):
    response = client.post("/auth/log-in", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == code