from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_auth_service
from app.schemas.auth import (
    LogInRequest,
    RegisterUserRequest,
    User,
    ErrorResponse,
    LogInBadRequest,
    RegisterUserBadRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=True,
    responses={
        400: {"model": RegisterUserBadRequest},
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
        400: {"model": LogInBadRequest},
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
