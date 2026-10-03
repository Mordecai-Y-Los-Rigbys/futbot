from unittest.mock import MagicMock
import bcrypt
import pytest
from fastapi import Response

from app.api.auth import user_login
from app.errors import ApiError
from app.models.user import User
from app.schemas.auth import LogInRequest
from app.services.auth_service import AuthService


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def mock_session_service():
    return MagicMock()


@pytest.fixture
def auth_service(mock_user_repo, mock_session_service):
    return AuthService(
        user_repo=mock_user_repo,
        session_service=mock_session_service,
        behavior_service=MagicMock(),
    )


# ==============================================================================
# PRUEBAS UNITARIAS: AuthService (Lógica de Negocio con Mocks)
# ==============================================================================

def test_auth_service_login_success(auth_service, mock_user_repo, mock_session_service):
    """Verifica login exitoso, llamada al repositorio y creación de sesión con mocks."""
    raw_password = "Password123!"
    hashed = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    dummy_user = User(
        id=1,
        username="usuario_test",
        email="user@test.com",
        password_hash=hashed,
        club_name="Mi Club",
    )
    mock_user_repo.get_by_email.return_value = dummy_user

    dummy_session = MagicMock()
    dummy_session.id = "session-uuid-valida"
    mock_session_service.create.return_value = dummy_session

    user, session_id = auth_service.login(email="user@test.com", password=raw_password)

    assert user.id == 1
    assert user.username == "usuario_test"
    assert user.club_name == "Mi Club"
    assert session_id == "session-uuid-valida"

    mock_user_repo.get_by_email.assert_called_once_with("user@test.com")
    mock_session_service.create.assert_called_once_with(user_id=1)


def test_auth_service_login_user_not_found_raises_401(auth_service, mock_user_repo, mock_session_service):
    """Verifica 401 si el email no existe y que no se cree sesión."""
    mock_user_repo.get_by_email.return_value = None

    with pytest.raises(ApiError) as exc_info:
        auth_service.login(email="inexistente@test.com", password="password123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.code is None
    assert exc_info.value.message == "Email o contraseña incorrectos."
    mock_session_service.create.assert_not_called()


def test_auth_service_login_wrong_password_raises_401(auth_service, mock_user_repo, mock_session_service):
    """Verifica 401 si la contraseña es incorrecta y que no se cree sesión."""
    hashed = bcrypt.hashpw(b"correct_password", bcrypt.gensalt()).decode("utf-8")
    dummy_user = User(
        id=1,
        username="testuser",
        email="user@test.com",
        password_hash=hashed,
        club_name="Mi Club",
    )
    mock_user_repo.get_by_email.return_value = dummy_user

    with pytest.raises(ApiError) as exc_info:
        auth_service.login(email="user@test.com", password="wrong_password")

    assert exc_info.value.status_code == 401
    assert exc_info.value.code is None
    assert exc_info.value.message == "Email o contraseña incorrectos."
    mock_session_service.create.assert_not_called()


def test_auth_service_login_password_over_72_chars_raises_401(auth_service, mock_user_repo, mock_session_service):
    """Verifica que una contraseña de 73 chars sea rechazada con 401 sin consultar al repo."""
    password_73 = "a" * 73

    with pytest.raises(ApiError) as exc_info:
        auth_service.login(email="user@test.com", password=password_73)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code is None
    assert exc_info.value.message == "Email o contraseña incorrectos."
    mock_user_repo.get_by_email.assert_not_called()
    mock_session_service.create.assert_not_called()


def test_auth_service_login_password_exact_72_chars_success(auth_service, mock_user_repo, mock_session_service):
    """Verifica que el límite de 72 caracteres exactos sea aceptado correctamente."""
    password_72 = "a" * 72
    hashed = bcrypt.hashpw(password_72.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    dummy_user = User(
        id=2,
        username="user72",
        email="limite72@test.com",
        password_hash=hashed,
        club_name="Club Limite",
    )
    mock_user_repo.get_by_email.return_value = dummy_user

    dummy_session = MagicMock()
    dummy_session.id = "session-72"
    mock_session_service.create.return_value = dummy_session

    user, session_id = auth_service.login(email="limite72@test.com", password=password_72)

    assert user.id == 2
    assert session_id == "session-72"
    mock_session_service.create.assert_called_once_with(user_id=2)


def test_auth_service_login_password_with_spaces_not_trimmed(auth_service, mock_user_repo, mock_session_service):
    """Verifica que las contraseñas con espacios no se recorten ni alteren antes de verificar."""
    pass_with_spaces = "  password con espacios  "
    hashed = bcrypt.hashpw(pass_with_spaces.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    dummy_user = User(
        id=3,
        username="user_spaces",
        email="spaces@test.com",
        password_hash=hashed,
        club_name="Club Espacios",
    )
    mock_user_repo.get_by_email.return_value = dummy_user

    # Con espacios recortados debe fallar con 401
    with pytest.raises(ApiError) as exc_info:
        auth_service.login(email="spaces@test.com", password=pass_with_spaces.strip())
    assert exc_info.value.status_code == 401

    # Con los espacios exactos debe autenticar
    dummy_session = MagicMock()
    dummy_session.id = "session-spaces"
    mock_session_service.create.return_value = dummy_session

    user, session_id = auth_service.login(email="spaces@test.com", password=pass_with_spaces)
    assert user.id == 3
    assert session_id == "session-spaces"


# ==============================================================================
# PRUEBAS UNITARIAS: Controlador API (Mockeando AuthService)
# ==============================================================================

def test_endpoint_user_login_delegates_to_service_and_sets_cookie():
    """Valida que el endpoint llame a AuthService y setee la cookie en Response."""
    mock_service = MagicMock()
    dummy_user = User(
        id=5,
        username="apiuser",
        email="api@test.com",
        password_hash="hashed_secret",
        club_name="Api FC",
    )
    mock_service.login.return_value = (dummy_user, "mock-cookie-session-id")

    req = LogInRequest(email="api@test.com", password="password123")
    mock_response = MagicMock(spec=Response)

    result = user_login(request=req, response=mock_response, auth_service=mock_service)

    mock_service.login.assert_called_once_with(email="api@test.com", password="password123")
    mock_response.set_cookie.assert_called_once_with(
        key="session_id",
        value="mock-cookie-session-id",
        httponly=True,
        samesite="lax",
    )

    # Verifica que el cuerpo expuesto contenga los datos esperados y no exponga contraseñas
    assert result.id == 5
    assert result.username == "apiuser"
    assert result.club_name == "Api FC"
    assert not hasattr(result, "password")
    assert not hasattr(result, "password_hash")