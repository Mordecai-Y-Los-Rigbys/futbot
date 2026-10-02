from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id, get_player_service
from app.api.pagination import parse_page
from app.schemas.errors import Error, ListPageBadRequest
from app.schemas.player import PlayerPage, PlayerResponse
from app.services.player_service import PAGE_SIZE, PlayerService

router = APIRouter(prefix="/players", tags=["players"])


@router.get(
    "/me",
    response_model=PlayerPage,
    responses={
        400: {"model": ListPageBadRequest},
        401: {"model": Error},
    },
)
def get_my_players(
    name: str | None = Query(default=None),
    page: str = Query(default="1"),
    user_id: int = Depends(get_current_user_id),  
    service: PlayerService = Depends(get_player_service),
):
    page_number = parse_page(page)
    items, total = service.get_user_players(user_id, name, page_number)
    return PlayerPage(
        items=items,
        page=page_number,
        pageSize=PAGE_SIZE,
        total=total,
    )