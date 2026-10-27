import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from starlette.concurrency import run_in_threadpool

from app.api.deps import (
    CurrentSession,
    get_current_session,
    get_current_user_id,
    get_json_body,
    get_league_service,
)
from app.api.pagination import parse_page
from app.schemas.errors import (
    CreateLeagueBadRequest,
    CreateLeagueConflict,
    Error,
    JoinLeagueConflict,
    JoinLeagueForbidden,
    ListPageBadRequest,
    ValidationBadRequest,
)
from app.schemas.league import LeaguePage, LeagueSummary
from app.services.league_participants_broadcast import (
    LeagueParticipantsPublisher,
    get_league_participants_publisher,
)
from app.services.league_service import LeagueService

logger = logging.getLogger(__name__)

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


@router.post(
    "/{id}/participants",
    status_code=201,
    response_class=Response,
    operation_id="joinLeague",
    summary="Inscribirse a una liga con un equipo",
    responses={
        201: {"description": "Inscripción realizada."},
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": JoinLeagueForbidden},
        404: {"model": Error},
        409: {"model": JoinLeagueConflict},
    },
)
async def join_league(
    id: str,
    session: CurrentSession = Depends(get_current_session),  # 401 primero
    body: Any = Depends(get_json_body),
    service: LeagueService = Depends(get_league_service),
    publisher: LeagueParticipantsPublisher = Depends(get_league_participants_publisher),
) -> Response:
    league_id = await run_in_threadpool(service.join_league, session.user_id, session.id, id, body)

    # Solo se llega acá con la inscripción ya confirmada en la base: una
    # solicitud fallida no emite nada. Si la emisión falla, la inscripción
    # sigue siendo válida: se registra el error y se responde 201 igual.
    try:
        await publisher.publish(league_id)
    except Exception:
        logger.exception("No se pudieron emitir los participantes de la liga %s", league_id)

    return Response(status_code=201)
