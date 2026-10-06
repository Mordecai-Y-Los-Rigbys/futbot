from unittest.mock import MagicMock

import pytest

from app.errors import ApiError
from app.models.user import User
from app.schemas.auth import RegisterUserRequest
from app.services.auth_service import AuthService


def make_request() -> RegisterUserRequest:
    return RegisterUserRequest(
        username="messi",
        email="messi@test.com",
        password="Password123!",
        clubName="Inter",
        avatar=1,
    )


@pytest.fixture
def deps():
    """Un mock padre para los tres colaboradores: registra el orden de todas las llamadas."""
    parent = MagicMock()
    parent.user_repo.get_by_email.return_value = None
    parent.user_repo.create.return_value = User(
        id=7,
        username="messi",
        email="messi@test.com",
        password_hash="h",
        club_name="Inter",
        avatar=1,
    )
    parent.session_service.create.return_value.id = "session-id"
    return parent


@pytest.fixture
def service(deps):
    return AuthService(
        user_repo=deps.user_repo,
        session_service=deps.session_service,
        behavior_service=deps.behavior_service,
    )


def test_register_creates_the_default_behaviors_for_the_new_user(service, deps):
    service.register(make_request())

    deps.behavior_service.create_default_behaviors.assert_called_once_with(7)


def test_behaviors_are_created_after_the_user_and_before_the_session(service, deps):
    service.register(make_request())

    calls = [c[0] for c in deps.mock_calls]
    assert (
        calls.index("user_repo.create")
        < calls.index("behavior_service.create_default_behaviors")
        < calls.index("session_service.create")
    )


def test_if_the_behaviors_fail_no_session_is_created(service, deps):
    deps.behavior_service.create_default_behaviors.side_effect = RuntimeError("falló")

    with pytest.raises(RuntimeError):
        service.register(make_request())

    deps.session_service.create.assert_not_called()


def test_duplicate_email_creates_no_behaviors(service, deps):
    deps.user_repo.get_by_email.return_value = User(id=1, email="messi@test.com")

    with pytest.raises(ApiError):
        service.register(make_request())

    deps.behavior_service.create_default_behaviors.assert_not_called()
