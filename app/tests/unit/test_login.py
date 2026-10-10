import json
import uuid
from types import SimpleNamespace
 
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
 
from app.errors import ApiError, api_error_handler, validation_exception_handler
from app.repositories.user_abstract import AbstractUserRepository
from app.schemas.auth import LogInRequest
from app.services.auth_service import AuthService
from app.services.security_service import hash_password
 
URL = "/auth/log-in"
 
# Orden del schema LogInRequest (convención 6.g y convención 9)
SCHEMA_ORDER = ["email", "password"]
 
UNREADABLE_KINDS = ["broken_json", "no_body", "null", "array", "string", "number"]
 
UNAUTHORIZED_MESSAGE = "Email o contraseña incorrectos."
UNAUTHORIZED_BODY = {"code": None, "message": UNAUTHORIZED_MESSAGE}
 
 
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
 
 
# ------------------------------------------------------------------
# Fakes en memoria (sin base de datos)
# ------------------------------------------------------------------
 
 
class FakeUserRepo(AbstractUserRepository):
    def __init__(self) -> None:
        self.users: dict[str, SimpleNamespace] = {}
        self.lookups = 0
 
    def add(self, email: str, password_hash: str, username="messi", club_name="Inter Miami"):
        user = SimpleNamespace(
            id=len(self.users) + 1,
            username=username,
            email=email,
            password_hash=password_hash,
            club_name=club_name,
            avatar=3,
        )
        self.users[email] = user
        return user
 
    def get_by_email(self, email: str):
        self.lookups += 1
        return self.users.get(email)
 
    def get_by_id(self, user_id: int):
        return next((u for u in self.users.values() if u.id == user_id), None)
 
    def create(self, username, email, password_hash, club_name, avatar):
        raise NotImplementedError("el login no crea usuarios")
 
 
class FakeSessionService:
    def __init__(self) -> None:
        self.created: list[int] = []  # user_id de cada sesión creada
 
    def create(self, user_id: int):
        self.created.append(user_id)
        return SimpleNamespace(id=f"session-{len(self.created)}")
 
 
# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
 
 
@pytest.fixture(scope="module")
def password_hash():
    """Hashea con el bcrypt real una sola vez por contraseña (es lento)."""
    cache: dict[str, str] = {}
 
    def get(password: str) -> str:
        if password not in cache:
            cache[password] = hash_password(password)
        return cache[password]
 
    return get
 
 
@pytest.fixture
def world(password_hash):
    """Repositorio y sesiones falsos, con el AuthService real encima."""
    repo = FakeUserRepo()
    sessions = FakeSessionService()
    service = AuthService(user_repo=repo, session_service=sessions, behavior_service=None)
    return SimpleNamespace(repo=repo, sessions=sessions, service=service, hash=password_hash)
 
 
@pytest.fixture
def api(world):
    """El router real de auth con el AuthService falso inyectado."""
    # Los imports van acá adentro: si cambia la ruta del módulo, fallan solo
    # los tests del router y no todo el archivo.
    from app.api.auth import router
    from app.api.deps import get_auth_service
 
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.dependency_overrides[get_auth_service] = lambda: world.service
 
    world.client = TestClient(app)
    return world
 
 
@pytest.fixture(scope="module")
def validation_client():
    """App mínima: solo validación del request, sin servicios."""
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
 
    @app.post(URL)
    def login(body: LogInRequest):
        return {"ok": True}
 
    return TestClient(app)
 
 
@pytest.fixture(scope="module")
def prefixed_validation_client():
    """Mismo handler, pero con el router montado bajo un prefijo."""
    router = APIRouter(prefix="/api")
 
    @router.post(URL)
    def login(body: LogInRequest):
        return {"ok": True}
 
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    return TestClient(app)
 
 
# ==================================================================
# A) VALIDACIÓN
# ==================================================================
 
# -- Camino feliz ------------------------------------------------
 
 
def test_valid_body_passes_validation(validation_client):
    assert validation_client.post(URL, json=credentials()).status_code == 200
 
 
def test_valid_email_of_255_characters_passes_validation(validation_client):
    # Un email que register acepta tiene que poder iniciar sesión
    response = validation_client.post(URL, json=credentials(email=build_email(255)))
 
    assert response.status_code == 200
 
 
@pytest.mark.parametrize("length", [72, 73, 300])
def test_password_has_no_max_length_in_validation(validation_client, length):
    # Una contraseña larga debe llegar al servicio y responder 401, nunca 400
    response = validation_client.post(URL, json=credentials(password="p" * length))
 
    assert response.status_code == 200
 
 
def test_unknown_fields_are_ignored(validation_client):
    assert validation_client.post(URL, json=credentials(isAdmin=True)).status_code == 200
 
 
# -- Un reason por campo, con la precedencia del contrato ---------
 
 
@pytest.mark.parametrize("field", SCHEMA_ORDER)
def test_missing_field_is_required(validation_client, field):
    response = validation_client.post(URL, json=without(credentials(), field))
 
    assert_validation_error(response, {field: "required"})
 
 
@pytest.mark.parametrize("field", SCHEMA_ORDER)
def test_empty_string_is_required(validation_client, field):
    response = validation_client.post(URL, json=credentials(**{field: ""}))
 
    assert_validation_error(response, {field: "required"})
 
 
@pytest.mark.parametrize("field", SCHEMA_ORDER)
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
def test_field_with_wrong_type_is_invalid_type(validation_client, field, value):
    response = validation_client.post(URL, json=credentials(**{field: value}))
 
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
    response = validation_client.post(URL, json=credentials(email=email))
 
    assert_validation_error(response, {"email": "invalidEmail"})
 
 
def test_invalid_email_is_not_evaluated_when_presence_or_type_failed(validation_client):
    # Precedencia required > invalidType > invalidEmail (convención 6.e)
    assert_validation_error(
        validation_client.post(URL, json=credentials(email="")), {"email": "required"}
    )
    assert_validation_error(
        validation_client.post(URL, json=credentials(email=123)), {"email": "invalidType"}
    )
 
 
# -- Formato del 400 ---------------------------------------------
 
 
def test_400_has_the_contract_shape(validation_client):
    response = validation_client.post(URL, json=credentials(password=""))
 
    assert response.status_code == 400
    body = response.json()
    assert set(body) == {"code", "message", "errors"}
    assert body["code"] == "invalidFields"
    assert isinstance(body["message"], str) and body["message"]
    assert body["errors"] == [{"field": "password", "reason": "required"}]
 
 
def test_every_failing_field_is_reported_once_in_schema_order(validation_client):
    # El body trae los campos en orden inverso: el orden de `errors` es el del schema
    response = validation_client.post(URL, json={"password": 123, "email": "no-es-un-email"})
 
    assert response.status_code == 400
    assert errors_of(response) == [
        {"field": "email", "reason": "invalidEmail"},
        {"field": "password", "reason": "invalidType"},
    ]
 
 
def test_example_from_the_ticket_invalid_email_and_missing_password(validation_client):
    response = validation_client.post(URL, json={"email": "no-es-un-email"})
 
    assert errors_of(response) == [
        {"field": "email", "reason": "invalidEmail"},
        {"field": "password", "reason": "required"},
    ]
 
 
def test_empty_object_reports_both_fields_required_in_order(validation_client):
    assert_all_required(validation_client.post(URL, json={}))
 
 
def test_login_never_reports_too_long(validation_client):
    # El contrato no define tooLong para login
    response = validation_client.post(
        URL, json=credentials(email="a" * 300, password="p" * 300)
    )
 
    assert response.status_code == 400
    assert "tooLong" not in {e["reason"] for e in errors_of(response)}
 
 
# -- Body ilegible (convención 9) --------------------------------
 
 
@pytest.mark.parametrize("kind", UNREADABLE_KINDS)
def test_unreadable_body_reports_email_and_password_required(validation_client, kind):
    assert_all_required(post_unreadable(validation_client, kind))
 
 
def test_handler_applies_under_a_router_prefix(prefixed_validation_client):
    response = prefixed_validation_client.post("/api" + URL, json={"email": "a@b.com"})
 
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert errors_of(response) == [{"field": "password", "reason": "required"}]
 
 
# ==================================================================
# B) SERVICIO (AuthService.login con fakes y bcrypt real)
# ==================================================================
 
 
def test_service_returns_the_user_and_creates_one_session(world):
    user = world.repo.add("a@test.com", world.hash("Password123!"))
 
    returned_user, session_id = world.service.login("a@test.com", "Password123!")
 
    assert returned_user is user
    assert session_id == "session-1"
    assert world.sessions.created == [user.id]
 
 
@pytest.mark.parametrize(
    "password",
    [
        pytest.param("p" * 72, id="72-ascii"),
        pytest.param("ñ" * 72, id="72-chars-multibyte"),
    ],
)
def test_service_accepts_a_password_of_exactly_72_characters(world, password):
    world.repo.add("a@test.com", world.hash(password))
 
    _, session_id = world.service.login("a@test.com", password)
 
    assert session_id == "session-1"
 
 
def test_service_does_not_trim_the_password(world):
    # El ticket: "no se modifica ni recorta la contraseña antes de verificarla"
    world.repo.add("a@test.com", world.hash("  Clave123  "))
 
    with pytest.raises(ApiError) as exc:
        world.service.login("a@test.com", "Clave123")
    assert exc.value.status_code == 401
 
    _, session_id = world.service.login("a@test.com", "  Clave123  ")
    assert session_id == "session-1"
 
 
@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param("nadie@test.com", "Password123!", id="email-no-registrado"),
        pytest.param("a@test.com", "Incorrecta123!", id="contrasena-incorrecta"),
        pytest.param("a@test.com", "p" * 73, id="contrasena-de-73"),
        pytest.param("a@test.com", "p" * 300, id="contrasena-de-300"),
    ],
)
def test_service_rejects_invalid_credentials_with_the_same_401(world, email, password):
    world.repo.add("a@test.com", world.hash("p" * 72))
 
    with pytest.raises(ApiError) as exc:
        world.service.login(email, password)
 
    assert exc.value.status_code == 401
    assert exc.value.code is None
    assert exc.value.message == UNAUTHORIZED_MESSAGE
    assert world.sessions.created == []  # un rechazo no crea sesión
 
 
def test_service_creates_the_session_for_the_right_user(world):
    world.repo.add("a@test.com", world.hash("ClaveDeA123"))
    user_b = world.repo.add("b@test.com", world.hash("ClaveDeB456"))
 
    world.service.login("b@test.com", "ClaveDeB456")
 
    assert world.sessions.created == [user_b.id]
 
 
# ==================================================================
# C) ROUTER (router real + AuthService falso inyectado)
# ==================================================================
 
# -- 200 ---------------------------------------------------------
 
 
def test_router_login_returns_200_with_only_public_user_data(api):
    user = api.repo.add("a@test.com", api.hash("Password123!"), username="messi", club_name="Inter Miami")
 
    response = api.client.post(URL, json={"email": "a@test.com", "password": "Password123!"})
 
    assert response.status_code == 200
    assert response.json() == {"id": user.id, "username": "messi", "clubName": "Inter Miami"}
 
 
def test_router_login_sets_the_session_cookie(api):
    api.repo.add("a@test.com", api.hash("Password123!"))
 
    response = api.client.post(URL, json={"email": "a@test.com", "password": "Password123!"})
 
    assert response.cookies.get("session_id") == "session-1"
 
 
def test_router_login_never_exposes_the_password_or_its_hash(api):
    api.repo.add("a@test.com", api.hash("Password123!"))
 
    response = api.client.post(URL, json={"email": "a@test.com", "password": "Password123!"})
 
    assert "Password123!" not in response.text
    assert "$2" not in response.text  # prefijo de un hash bcrypt
    assert "password" not in response.json()
 
 
def test_router_session_belongs_to_the_user_who_logged_in(api):
    api.repo.add("a@test.com", api.hash("ClaveDeA123"))
    user_b = api.repo.add("b@test.com", api.hash("ClaveDeB456"), username="otro")
 
    response = api.client.post(URL, json={"email": "b@test.com", "password": "ClaveDeB456"})
 
    assert response.json()["id"] == user_b.id
    assert api.sessions.created == [user_b.id]
 
 
def test_router_user_with_a_255_character_email_can_log_in(api):
    email = build_email(255)
    api.repo.add(email, api.hash("Password123!"))
 
    response = api.client.post(URL, json={"email": email, "password": "Password123!"})
 
    assert response.status_code == 200
 
 
# -- 401 ---------------------------------------------------------
 
 
@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param("nadie@test.com", "Password123!", id="email-no-registrado"),
        pytest.param("a@test.com", "Incorrecta123!", id="contrasena-incorrecta"),
        pytest.param("a@test.com", "p" * 73, id="contrasena-de-73"),
        pytest.param("a@test.com", "p" * 300, id="contrasena-de-300"),
    ],
)
def test_router_invalid_credentials_return_the_same_401_and_no_cookie(api, email, password):
    api.repo.add("a@test.com", api.hash("p" * 72))
 
    response = api.client.post(URL, json={"email": email, "password": password})
 
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
    assert "session_id" not in response.cookies
    assert api.sessions.created == []
 
 
# -- 400 ---------------------------------------------------------
 
 
def test_router_400_has_no_cookie_and_never_reaches_the_service(api):
    api.repo.add("a@test.com", api.hash("Password123!"))
 
    response = api.client.post(URL, json={"email": "no-es-un-email", "password": ""})
 
    assert response.status_code == 400
    assert errors_of(response) == [
        {"field": "email", "reason": "invalidEmail"},
        {"field": "password", "reason": "required"},
    ]
    assert "session_id" not in response.cookies
    assert api.repo.lookups == 0
    assert api.sessions.created == []
 
 
@pytest.mark.parametrize("kind", UNREADABLE_KINDS)
def test_router_unreadable_body_reports_both_fields_required(api, kind):
    assert_all_required(post_unreadable(api.client, kind))
    assert api.repo.lookups == 0
 
 
def test_router_validation_error_takes_precedence_over_unauthorized(api):
    # Convención 4: el 400 se evalúa antes que el 401 de credenciales.
    # El email no está registrado, pero el password vacío se rechaza primero.
    response = api.client.post(URL, json=credentials(password=""))
 
    assert_validation_error(response, {"password": "required"})