from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import (
    CurrentSession,
    get_current_session,
    get_current_user_id,
    get_json_body,
    get_match_behavior_service,
    get_match_connection_service,
    get_match_service,
    get_match_team_service,
    get_substitution_service,
    get_match_player_behavior_service  
)
from app.helpers.ids import parse_path_id
from app.schemas.errors import (
    Error,
    JoinMatchConflict,
    JoinMatchForbidden,
    SubstitutePlayerConflict,
    SubstitutionsConflict,
    MatchAccessForbidden,
    MatchBehaviorConflict,
    MatchBehaviorForbidden,
    ValidationBadRequest,
)
from app.schemas.friendly import MatchResponse
from app.schemas.lineup import MatchLineups
from app.schemas.match_behavior import MatchPlayerBehavior
from app.schemas.match_connection import JoinMatchResponse
from app.schemas.match_team import MatchTeam, MatchTeamForbidden
from app.schemas.substitution import Substitutions
from app.services.match_behavior_service import MatchBehaviorService
from app.services.match_connection_service import MatchConnectionService
from app.services.match_player_behavior_service import MatchPlayerBehaviorService
from app.services.match_service import MATCH_NOT_FOUND_MESSAGE, MatchService
from app.services.match_team_service import MatchTeamService
from app.services.substitution_service import SubstitutionService

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get(
    "/{match_id}",
    response_model=MatchResponse,
    operation_id="getMatch",
    summary="Obtener un partido (clubes, usuarios, estado y resultado)",
    responses={
        401: {"model": Error},
        403: {"model": MatchAccessForbidden},
        404: {"model": Error},
    },
)
def get_match(
    match_id: str,
    session: CurrentSession = Depends(get_current_session),
    service: MatchService = Depends(get_match_service),
) -> MatchResponse:
    return service.get_match(
        parse_path_id(match_id, MATCH_NOT_FOUND_MESSAGE), session.id, session.user_id
    )


@router.get(
    "/{match_id}/lineups",
    response_model=MatchLineups,
    operation_id="getMatchLineups",
    summary="Obtener los titulares de ambos clubes de un partido",
    responses={
        401: {"model": Error},
        403: {"model": MatchAccessForbidden},
        404: {"model": Error},
    },
)
def get_match_lineups(
    match_id: str,
    session: CurrentSession = Depends(get_current_session),
    service: MatchService = Depends(get_match_service),
) -> MatchLineups:
    return service.get_lineups(
        parse_path_id(match_id, MATCH_NOT_FOUND_MESSAGE), session.id, session.user_id
    )


@router.get(
    "/{match_id}/team",
    response_model=MatchTeam,
    operation_id="getMatchTeam",
    summary="Obtener el equipo del usuario en un partido",
    responses={
        401: {"model": Error},
        403: {"model": MatchTeamForbidden},
        404: {"model": Error},
    },
)
def get_match_team(
    match_id: str,  # str y no int: un "abc" daría 422 antes de llegar acá
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    service: MatchTeamService = Depends(get_match_team_service),
) -> MatchTeam:
    return service.get_team(user_id, parse_path_id(match_id, "El partido no existe."))


@router.post(
    "/{match_id}/connections",
    response_model=JoinMatchResponse,
    status_code=201,
    operation_id="joinMatch",
    summary="Crear una conexión a un partido y obtener el token del WebSocket",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": JoinMatchForbidden},
        404: {"model": Error},
        409: {"model": JoinMatchConflict},
    },
)
def join_match(
    match_id: str,  # str y no int: un "abc" daría 422 antes de llegar acá
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    body: Any = Depends(get_json_body),
    service: MatchConnectionService = Depends(get_match_connection_service),
) -> JoinMatchResponse:
    conn = service.connect(user_id, parse_path_id(match_id, "El partido no existe."), body)
    return JoinMatchResponse(token_ws=conn.token, role=conn.role)


@router.get(
    "/{match_id}/substitutions",
    response_model=Substitutions,
    operation_id="getMatchSubstitutions",
    summary="Obtener la sustitución de cada equipo de un partido en juego (aplicada durante una pausa, pendiente fuera de ella)",
    responses={
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": SubstitutionsConflict},
    },
)
def get_substitutions(
    match_id: str,  # str y no int: un "abc" daría 422 antes de llegar acá
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    service: SubstitutionService = Depends(get_substitution_service),
) -> Substitutions:
    return service.get_substitutions(user_id, parse_path_id(match_id, "El partido no existe."))


@router.put(
    "/{match_id}/substitutions",
    status_code=204,
    response_class=Response,
    operation_id="setMatchSubstitution",
    summary="Pedir una sustitución para el equipo del usuario",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": SubstitutePlayerConflict},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["starterId", "substituteId"],
                        "properties": {
                            "starterId": {"type": "integer", "minimum": 1, "maximum": 2147483647},
                            "substituteId": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 2147483647,
                            },
                        },
                    }
                }
            },
        }
    },
)
def request_substitution(
    match_id: str,
    user_id: int = Depends(get_current_user_id),
    body: Any = Depends(get_json_body),
    service: SubstitutionService = Depends(get_substitution_service),
) -> Response:
    service.request_substitution(user_id, parse_path_id(match_id, "El partido no existe."), body)
    return Response(status_code=204)


@router.get(
    "/{match_id}/behavior",
    response_model=MatchPlayerBehavior,
    operation_id="getMatchPlayerBehavior",
    summary="Obtener el behavior de un jugador durante el partido",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": MatchBehaviorForbidden},
        404: {"model": Error},
    },
)
def get_match_player_behavior(
    match_id: str,  # str y no int: un "abc" daría 422 antes de llegar acá
    player_id: str | None = Query(default=None, alias="playerId"),  # str: validado en el service
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    service: MatchPlayerBehaviorService = Depends(get_match_player_behavior_service),
) -> MatchPlayerBehavior:
    return service.get_behavior(
        user_id, parse_path_id(match_id, "El partido no existe."), player_id
    )

    
@router.put(
    "/{match_id}/behavior",
    status_code=204,
    response_class=Response,
    operation_id="reassignMatchBehavior",
    summary="Cambiar el behavior de un titular durante el partido",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": MatchBehaviorForbidden},
        404: {"model": Error},
        409: {"model": MatchBehaviorConflict},
    },
)
def reassign_match_behavior(
    match_id: str,
    user_id: int = Depends(get_current_user_id),
    body: Any = Depends(get_json_body),
    service: MatchBehaviorService = Depends(get_match_behavior_service),
) -> Response:
    service.reassign(user_id, parse_path_id(match_id, "El partido no existe."), body)
    return Response(status_code=204)
