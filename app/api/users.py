from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_user_service
from app.schemas.auth import ErrorResponse, User
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    operation_id="getCurrentUser",
    response_model=User,
    response_model_by_alias=True,
    responses={401: {"model": ErrorResponse}},
)
def get_current_user(
    user_id: int = Depends(get_current_user_id),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Devuelve id, username y clubName del usuario de la sesión actual."""
    return User.model_validate(user_service.get_by_id(user_id))
