from unittest.mock import MagicMock

import pytest
from fastapi import Response

from app.api.auth import register_user
from app.errors import ApiError
from app.models.user import User
from app.schemas.auth import RegisterUserRequest
from app.services import auth_service as auth_service_module
from app.services.auth_service import AuthService
from app.services.security_service import verify_password


def make_request(**over) -> RegisterUserRequest:
    data = dict(
        username="messi",
        email="messi@test.com",
        password="Password123!",
        clubName="Inter Miami",  # el schema usa alias camelCase
        avatar=3,
    )
    data.update(over)
    return RegisterUserRequest(**data)


@pytest.fixture
def user_repo():
    repo = MagicMock()
    repo.get_by_email.return_value = None  # por defecto, el email está libre
    repo.create.side_effect = lambda **kw: User(id=1, **kw)
    return repo


@pytest.fixture
def session_service():
    service = MagicMock()
    session = MagicMock()
    session.id = "session-id-123"
    service.create.return_value = session
    return service


@pytest.fixture
def auth_service(user_repo, session_service):
    return AuthService(user_repo=user_repo, session_service=session_service)


# ==============================================================================
# AuthService.register
# ==============================================================================

def test_register_returns_user_and_session_id(auth_service):
    user, session_id = auth_service.register(make_request())

    assert user.id == 1
    assert user.username == "messi"
    assert user.club_name == "Inter Miami"
    assert session_id == "session-id-123"


def test_register_checks_email_before_creating(auth_service, user_repo):
    auth_service.register(make_request(email="a@test.com"))

    user_repo.get_by_email.assert_called_once_with("a@test.com")
    user_repo.create.assert_called_once()


def test_register_passes_every_field_to_the_repository(auth_service, user_repo):
    auth_service.register(make_request(avatar=5))

    kwargs = user_repo.create.call_args.kwargs
    assert kwargs["username"] == "messi"
    assert kwargs["email"] == "messi@test.com"
    assert kwargs["club_name"] == "Inter Miami"  # clubName -> club_name
    assert kwargs["avatar"] == 5
    assert set(kwargs) == {"username", "email", "password_hash", "club_name", "avatar"}


def test_register_never_stores_the_plain_password(auth_service, user_repo):
    auth_service.register(make_request(password="Password123!"))

    stored = user_repo.create.call_args.kwargs["password_hash"]
    assert stored != "Password123!"
    assert verify_password("Password123!", stored)


def test_register_creates_a_session_for_the_new_user(auth_service, session_service):
    auth_service.register(make_request())

    session_service.create.assert_called_once_with(user_id=1)


def test_register_accepts_a_72_char_password(auth_service, user_repo):
    auth_service.register(make_request(password="a" * 72))

    stored = user_repo.create.call_args.kwargs["password_hash"]
    assert verify_password("a" * 72, stored)


def test_register_duplicate_email_raises_409(auth_service, user_repo, session_service):
    user_repo.get_by_email.return_value = User(id=9, email="messi@test.com")

    with pytest.raises(ApiError) as exc:
        auth_service.register(make_request())

    assert exc.value.status_code == 409
    assert exc.value.code is None
    assert exc.value.message
    user_repo.create.assert_not_called()
    session_service.create.assert_not_called()


def test_register_duplicate_email_does_not_hash_the_password(
    auth_service, user_repo, monkeypatch
):
    hash_mock = MagicMock()
    monkeypatch.setattr(auth_service_module, "hash_password", hash_mock)
    user_repo.get_by_email.return_value = User(id=9, email="messi@test.com")

    with pytest.raises(ApiError):
        auth_service.register(make_request())

    hash_mock.assert_not_called()  # bcrypt es caro: no se gasta si ya hay 409


def test_register_repository_failure_creates_no_session(
    auth_service, user_repo, session_service
):
    user_repo.create.side_effect = RuntimeError("db caída")

    with pytest.raises(RuntimeError):
        auth_service.register(make_request())

    session_service.create.assert_not_called()


# ==============================================================================
# Endpoint register_user (con AuthService mockeado)
# ==============================================================================

def test_endpoint_register_delegates_sets_cookie_and_hides_secrets():
    service = MagicMock()
    service.register.return_value = (
        User(id=5, username="apiuser", email="api@test.com",
             password_hash="hashed", club_name="Api FC"),
        "cookie-session-id",
    )
    request = make_request()
    response = MagicMock(spec=Response)

    result = register_user(request=request, response=response, auth_service=service)

    service.register.assert_called_once_with(request)
    response.set_cookie.assert_called_once_with(
        key="session_id",
        value="cookie-session-id",
        httponly=True,
        samesite="lax",
    )
    assert (result.id, result.username, result.club_name) == (5, "apiuser", "Api FC")
    assert not hasattr(result, "password")
    assert not hasattr(result, "password_hash")
    assert not hasattr(result, "email")


def test_endpoint_register_conflict_sets_no_cookie():
    service = MagicMock()
    service.register.side_effect = ApiError(409, None, "El email ya está asociado.")
    response = MagicMock(spec=Response)

    with pytest.raises(ApiError) as exc:
        register_user(request=make_request(), response=response, auth_service=service)

    assert exc.value.status_code == 409
    response.set_cookie.assert_not_called()