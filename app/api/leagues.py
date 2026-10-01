from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id, get_league_service
from app.api.pagination import parse_page
from app.schemas.errors import Error, ListPageBadRequest
from app.schemas.league import LeaguePage
from app.services.league_service import LeagueService

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get(
    "",
    response_model=LeaguePage,
    operation_id="listLeagues",
    summary="Listar ligas",
    responses={
        400: {"model": ListPageBadRequest},
        401: {"model": Error},
    },
)
def list_leagues(
    name: str | None = Query(default=None),
    page: str = Query(default="1"),
    _user_id: int = Depends(get_current_user_id),  # 401 antes que cualquier 400
    service: LeagueService = Depends(get_league_service),
) -> LeaguePage:
    return service.list_leagues(name=name, page=parse_page(page))