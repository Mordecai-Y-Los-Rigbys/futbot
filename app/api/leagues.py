from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id, get_json_body, get_league_service
from app.api.pagination import parse_page
from app.schemas.errors import (
    CreateLeagueBadRequest,
    CreateLeagueConflict,
    Error,
    ListPageBadRequest,
)
from app.schemas.league import LeaguePage, LeagueSummary
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


@router.post(
    "",
    response_model=LeagueSummary,
    status_code=201,
    operation_id="createLeague",
    summary="Crear una liga",
    responses={
        400: {"model": CreateLeagueBadRequest},
        401: {"model": Error},
        409: {"model": CreateLeagueConflict},
    },
)
def create_league(
    user_id: int = Depends(get_current_user_id),
    body: Any = Depends(get_json_body),
    service: LeagueService = Depends(get_league_service),
) -> LeagueSummary:
    return service.create_league(creator_id=user_id, body=body)