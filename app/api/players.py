from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_player_service
from app.schemas.errors import Error
from app.schemas.player import PlayerResponse
from app.services.player_service import PlayerService

router = APIRouter(prefix="/players", tags=["players"])


@router.get(
    "/me",
    response_model=list[PlayerResponse],
    operation_id="getMyPlayers",
    summary="Obtener la plantilla del usuario actual",
    responses={
        401: {"model": Error},
    },
)
def get_my_players(
    user_id: int = Depends(get_current_user_id),
    service: PlayerService = Depends(get_player_service),
) -> list[PlayerResponse]:
    return service.get_my_players(user_id)