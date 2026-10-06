from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from app.api.deps import get_session_service, get_user_service
from app.errors import ApiError
from app.repositories.user_abstract import AbstractUserRepository
from app.services.session_service import SessionService
from app.services.user_service import UserService

UNAUTHORIZED = {"code": None, "message": "Sin sesión válida."}


def make_user(id=7, username="mgonzalez", club_name="Boca Juniors FC"):
    # Tiene además campos que NO deben salir en la respuesta
    return SimpleNamespace(
        id=id,
        username=username,
        club_name=club_name,
        email="mgonzalez@test.com",
        password_hash="$2b$12$hash",
        avatar=3,
    )


# --- UserService --------------------------------------------------------------


@pytest.fixture
def user_repo():
    return create_autospec(AbstractUserRepository, instance=True)


def test_service_returns_the_user(user_repo):
    user = make_user()
    user_repo.get_by_id.return_value = user

    assert UserService(user_repo).get_by_id(7) is user
    user_repo.get_by_id.assert_called_once_with(7)


def test_service_missing_user_raises_401(user_repo):
    # sesión válida pero el usuario ya no existe -> igual que sesión inválida
    user_repo.get_by_id.return_value = None

    with pytest.raises(ApiError) as exc:
        UserService(user_repo).get_by_id(7)

    assert exc.value.status_code == 401
    assert exc.value.code is None
    assert exc.value.message == "Sin sesión válida."


# --- Endpoint -----------------------------------------------------------------


@pytest.fixture()
def user_service():
    return create_autospec(UserService, instance=True)


@pytest.fixture()
def users_api(api, user_service):
    """`api` (conftest unit) ya mockea las sesiones: 'valid-session' -> user 7.
    Acá se reemplaza además el UserService; `api` limpia los overrides al terminar."""
    from app.main import app

    app.dependency_overrides[get_user_service] = lambda: user_service
    return api


def test_success_returns_200_and_user_schema(users_api, user_service):
    user_service.get_by_id.return_value = make_user()
    users_api.cookies.set("session_id", "valid-session")

    response = users_api.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": 7,
        "username": "mgonzalez",
        "clubName": "Boca Juniors FC",
    }
    user_service.get_by_id.assert_called_once_with(7)


def test_success_field_types(users_api, user_service):
    user_service.get_by_id.return_value = make_user()
    users_api.cookies.set("session_id", "valid-session")

    data = users_api.get("/users/me").json()

    assert isinstance(data["id"], int)
    assert isinstance(data["username"], str)
    assert isinstance(data["clubName"], str)


def test_success_does_not_leak_private_fields(users_api, user_service):
    user_service.get_by_id.return_value = make_user()
    users_api.cookies.set("session_id", "valid-session")

    data = users_api.get("/users/me").json()

    assert set(data) == {"id", "username", "clubName"}
    assert "club_name" not in data


def test_missing_cookie_returns_401(users_api, user_service):
    response = users_api.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    user_service.get_by_id.assert_not_called()


def test_invalid_cookie_returns_401(users_api, user_service):
    users_api.cookies.set("session_id", "no-existe")

    response = users_api.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    user_service.get_by_id.assert_not_called()


def test_expired_cookie_returns_401(users_api, user_service):
    """Sesión vencida con el SessionService real y un repo en memoria."""
    from app.main import app

    repo = SimpleNamespace(
        get_by_id=lambda sid: SimpleNamespace(
            id=sid,
            user_id=7,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        ),
        delete=lambda sid: None,
    )
    app.dependency_overrides[get_session_service] = lambda: SessionService(repo)
    users_api.cookies.set("session_id", "vencida")

    response = users_api.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    user_service.get_by_id.assert_not_called()


def test_valid_session_but_user_deleted_returns_401(users_api, user_service):
    user_service.get_by_id.side_effect = ApiError(401, None, "Sin sesión válida.")
    users_api.cookies.set("session_id", "valid-session")

    response = users_api.get("/users/me")

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_401_has_priority_over_unexpected_query_params(users_api):
    response = users_api.get("/users/me?page=abc")

    assert response.status_code == 401
