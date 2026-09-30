import re

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id, get_league_service
from app.errors import ApiError
from app.schemas.league import LeaguePage
from app.services.league_service import LeagueService
from app.api.pagination import parse_page

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("", response_model=LeaguePage, operation_id="listLeagues")
def list_leagues(
    name: str | None = Query(default=None),
    page: str | None = Query(default=None),
    _user_id: int = Depends(get_current_user_id),  # 401 antes que cualquier 400
    service: LeagueService = Depends(get_league_service),
) -> LeaguePage:
    return service.list_leagues(name=name, page=parse_page(page))