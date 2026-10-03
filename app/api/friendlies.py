from typing import Any

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user_id, get_friendly_service, get_json_body
from app.api.pagination import parse_page
from app.api.ws_deps import get_friendly_expiry
from app.schemas.errors import (
    CreateFriendlyMatchBadRequest,
    CreateFriendlyMatchConflict,
    Error,
    ListPageBadRequest,
)
from app.schemas.friendly import MatchPage, MatchResponse
from app.services.friendly_expiry import FriendlyExpiryService
from app.services.friendly_service import FriendlyService

router = APIRouter(prefix="/friendlies", tags=["friendlies"])


@router.get(
    "",
    response_model=MatchPage,
    operation_id="listFriendlyMatches",
    summary="Listar partidos amistosos que esperan rival",
    responses={
        400: {"model": ListPageBadRequest},
        401: {"model": Error},
    },
)
def list_friendlies(
    name: str | None = Query(default=None),
    page: str = Query(default="1"),
    user_id: int = Depends(get_current_user_id),  # 401 antes que cualquier 400
    service: FriendlyService = Depends(get_friendly_service),
) -> MatchPage:
    return service.list_waiting_friendlies(
        user_id=user_id, name=name, page=parse_page(page)
    )


@router.post(
    "",
    response_model=MatchResponse,
    status_code=201,
    operation_id="createFriendlyMatch",
    summary="Crear un partido amistoso",
    responses={
        400: {"model": CreateFriendlyMatchBadRequest},
        401: {"model": Error},
        409: {"model": CreateFriendlyMatchConflict},
    },
)
async def create_friendly(
    user_id: int = Depends(get_current_user_id),
    body: Any = Depends(get_json_body),
    service: FriendlyService = Depends(get_friendly_service),
    expiry: FriendlyExpiryService = Depends(get_friendly_expiry),
) -> MatchResponse:
    # El servicio es sync (usa la DB): va al threadpool. schedule() necesita el
    # event loop, así que se llama acá, ya con el partido confirmado en la base.
    match = await run_in_threadpool(service.create_friendly, user_id, body)
    expiry.schedule(match.id, match.created_at)
    return match
