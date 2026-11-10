from fastapi import APIRouter, Depends, Response, status

from app.api.deps import (
    CurrentSession,
    get_auth_service,
    get_current_session,
    get_session_service,
)
from app.api.ws_league_deps import get_league_channel_managers
from app.schemas.auth import (
    LogInRequest,
    RegisterUserRequest,
    User,
    ErrorResponse,
)
from app.schemas.errors import ValidationBadRequest
from app.services.auth_service import AuthService
from app.services.league_channel_manager import LeagueChannelManager
from app.services.session_service import SessionService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=True,
    responses={
        400: {"model": ValidationBadRequest},
        409: {"model": ErrorResponse},
    },
)
def register_user(
    request: RegisterUserRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Registra un nuevo usuario delegando la creación y sesión a AuthService."""
    new_user, session_id = auth_service.register(request)

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
    )

    return User.model_validate(new_user)


@router.post(
    "/log-in",
    response_model=User,
    status_code=status.HTTP_200_OK,
    response_model_by_alias=True,
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": ErrorResponse},
    },
)
def user_login(
    request: LogInRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Autentica al usuario delegando la verificación y sesión a AuthService."""
    user, session_id = auth_service.login(
        email=request.email,
        password=request.password,
    )

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
    )

    return User.model_validate(user)


@router.post(
    "/log-out",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    operation_id="logOut",
    responses={401: {"model": ErrorResponse}},
)
def user_logout(
    session: CurrentSession = Depends(get_current_session),
    service: SessionService = Depends(get_session_service),
    channels: list[LeagueChannelManager] = Depends(get_league_channel_managers),
) -> Response:
    service.delete(session.id)
    # Cierra con 4401 sessionEnded los WebSockets de liga abiertos con esta sesión
    for manager in channels:
        manager.session_ended(session.id)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("session_id", httponly=True, samesite="lax")
    return response
