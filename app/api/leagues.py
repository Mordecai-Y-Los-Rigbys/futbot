from typing import Any

from fastapi import APIRouter, Depends, Query, Response

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
    LeaveLeagueConflict,
    ListPageBadRequest,
    ValidationBadRequest,
)
from app.helpers.ids import parse_path_id
from app.schemas.league import LeagueDetail, LeaguePage, LeagueSummary
from app.services.league_service import LeagueService, LEAGUE_NOT_FOUND_MESSAGE

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


@router.get(
    "/{league_id}",
    response_model=LeagueDetail,
    operation_id="getLeague",
    summary="Obtener una liga",
    responses={
        401: {"model": Error},
        404: {"model": Error},
    },
)
def get_league(
    league_id: str,
    user_id: int = Depends(get_current_user_id),  # 401 antes que 404
    service: LeagueService = Depends(get_league_service),
) -> LeagueDetail:
    return service.get_league(
        league_id=parse_path_id(league_id, LEAGUE_NOT_FOUND_MESSAGE),
        user_id=user_id,
    )
    
    
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



@router.delete(
    "/{id}/participants/me",
    status_code=204,
    response_class=Response,
    operation_id="leaveLeague",
    summary="Abandonar una liga",
    responses={
        401: {"model": Error},
        404: {"model": Error},
        409: {"model": LeaveLeagueConflict},
    },
)
def leave_league(
    id: str,
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    service: LeagueService = Depends(get_league_service),
) -> Response:
    service.leave_league(user_id=user_id, raw_league_id=id)
    return Response(status_code=204)

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
def join_league(
    id: str,  # str: un id inválido es 404 (lo decide el servicio), nunca 422
    session: CurrentSession = Depends(get_current_session),  # 401 antes que todo
    body: Any = Depends(get_json_body),
    service: LeagueService = Depends(get_league_service),
) -> Response:
    service.join_league(user_id=session.user_id, session_id=session.id, raw_league_id=id, body=body)
    return Response(status_code=201)
