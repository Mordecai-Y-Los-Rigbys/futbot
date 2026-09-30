from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.schemas.auth import RegisterUserRequest, UserResponse
from app.services.security_service import hash_password
from app.services.session_service import SessionService
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=True,
)
def register_user(
    request: RegisterUserRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Registra un nuevo usuario, hashea la contraseña y establece una sesión"""
    
    user_repo = UserRepository(db)

    if user_repo.get_by_email(request.email) is not None:
        raise ApiError(status_code=409, code=None, message="El email ya está asociado a otro usuario.")

    password_hash = hash_password(request.password)
    new_user = user_repo.create(
        username=request.username,
        email=request.email,
        password_hash=password_hash,
        club_name=request.club_name,
        avatar=request.avatar
    )

    session_service = SessionService(db)
    user_session = session_service.create(user_id=new_user.id)

    response.set_cookie(
        key="session_id",
        value=user_session.id,
        httponly=True,
        samesite="lax",
    )

    return UserResponse.model_validate(new_user)