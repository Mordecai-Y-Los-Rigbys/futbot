from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from starlette.concurrency import run_in_threadpool

from app.api.deps import (
    CurrentSession,
    get_current_session,
    get_current_user_id,
    get_json_body,
    get_league_access_service,
    get_league_service,
    get_ranking_service,
)
from app.api.league_access import router as league_access_router
from app.api.pagination import parse_page
from app.api.ws_deps import get_league_match_start
from app.helpers.ids import parse_path_id
from app.schemas.errors import (
    CreateLeagueConflict,
    Error,
    JoinLeagueConflict,
    JoinLeagueForbidden,
    LeagueDataConflict,
    LeaveLeagueConflict,
    StartLeagueConflict,
    ValidationBadRequest,
)
from app.schemas.friendly import MatchResponse
from app.schemas.league import LeagueDetail, LeaguePage, LeagueParticipant, LeagueSummary
from app.schemas.league_access import LeagueAccessForbidden
from app.schemas.ranking import LeagueRankingEntry
from app.services.league_access_service import LeagueAccessService
from app.services.league_match_start import LeagueMatchStartService
from app.services.ranking_service import RankingService
from app.services.league_service import LeagueService, LEAGUE_NOT_FOUND_MESSAGE

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get(
    "",
    response_model=LeaguePage,
    operation_id="listLeagues",
    summary="Listar ligas",
    responses={
        400: {"model": ValidationBadRequest},
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
        400: {"model": ValidationBadRequest},
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
    id: str,
    session: CurrentSession = Depends(get_current_session),  # 401 antes que todo
    body: Any = Depends(get_json_body),
    service: LeagueService = Depends(get_league_service),
) -> Response:
    service.join_league(user_id=session.user_id, session_id=session.id, raw_league_id=id, body=body)
    return Response(status_code=201)


@router.get(
    "/{id}/participants",
    response_model=list[LeagueParticipant],
    operation_id="listLeagueParticipants",
    summary="Listar los participantes inscriptos en una liga",
    responses={
        401: {"model": Error},
        403: {"model": LeagueAccessForbidden},
        404: {"model": Error},
    },
)
def list_league_participants(
    id: str,
    session: CurrentSession = Depends(get_current_session),  # 401 antes que todo
    access: LeagueAccessService = Depends(get_league_access_service),
    service: LeagueService = Depends(get_league_service),
) -> list[LeagueParticipant]:
    league = access.get_league(parse_path_id(id, LEAGUE_NOT_FOUND_MESSAGE))  # 404
    access.require_access(session.id, session.user_id, league)  # 403
    return service.list_participants(league.id)


@router.get(
    "/{id}/ranking",
    response_model=list[LeagueRankingEntry],
    operation_id="getLeagueRanking",
    summary="Obtener el ranking de una liga",
    responses={
        401: {"model": Error},
        403: {"model": LeagueAccessForbidden},
        404: {"model": Error},
        409: {"model": LeagueDataConflict},
    },
)
def get_league_ranking(
    id: str,
    session: CurrentSession = Depends(get_current_session),  # 401 antes que todo
    access: LeagueAccessService = Depends(get_league_access_service),
    service: RankingService = Depends(get_ranking_service),
) -> list[LeagueRankingEntry]:
    league = access.get_league(parse_path_id(id, LEAGUE_NOT_FOUND_MESSAGE))  # 404
    access.require_access(session.id, session.user_id, league)  # 403
    return service.get_league_ranking(league.id)


@router.get(
    "/{id}/fixture",
    response_model=list[MatchResponse],
    operation_id="getLeagueFixture",
    summary="Obtener el fixture de una liga",
    responses={
        401: {"model": Error},
        403: {"model": LeagueAccessForbidden},
        404: {"model": Error},
        409: {"model": LeagueDataConflict},
    },
)
def get_league_fixture(
    id: str,
    session: CurrentSession = Depends(get_current_session),  # 401 antes que todo
    access: LeagueAccessService = Depends(get_league_access_service),
    service: LeagueService = Depends(get_league_service),
) -> list[MatchResponse]:
    league = access.get_league(parse_path_id(id, LEAGUE_NOT_FOUND_MESSAGE))  # 404
    access.require_access(session.id, session.user_id, league)  # 403
    return service.get_fixture(league.id)  # 409


@router.post(
    "/{id}/start",
    status_code=204,
    response_class=Response,
    operation_id="startLeague",
    summary="Iniciar una liga",
    responses={
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": StartLeagueConflict},
    },
)
async def start_league(
    id: str,
    user_id: int = Depends(get_current_user_id),
    service: LeagueService = Depends(get_league_service),
    match_start: LeagueMatchStartService = Depends(get_league_match_start),
) -> Response:
    parsed_id = parse_path_id(id, LEAGUE_NOT_FOUND_MESSAGE)
    await run_in_threadpool(service.start_league, parsed_id, user_id)
    await match_start.schedule_league(parsed_id)
    return Response(status_code=204)


@router.get(
    "/{id}/fixture",
    response_model=list[MatchResponse],
    operation_id="getLeagueFixture",
    summary="Obtener el fixture de una liga",
    responses={
        401: {"model": Error},
        403: {"model": LeagueAccessForbidden},
        404: {"model": Error},
        409: {"model": LeagueDataConflict},
    },
)
def get_league_fixture(
    id: str,
    session: CurrentSession = Depends(get_current_session),  # 401 antes que todo
    access: LeagueAccessService = Depends(get_league_access_service),
    service: LeagueService = Depends(get_league_service),
) -> list[MatchResponse]:
    league = access.get_league(parse_path_id(id, LEAGUE_NOT_FOUND_MESSAGE))  # 404
    access.require_access(session.id, session.user_id, league)  # 403
    return service.get_fixture(league.id)  # 409


router.include_router(league_access_router)
