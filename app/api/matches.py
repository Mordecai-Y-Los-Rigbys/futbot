from typing import Any

from fastapi import APIRouter, Depends, Response

from app.api.deps import (
    get_current_user_id,
    get_json_body,
    get_match_connection_service,
    get_substitution_service
)
from app.helpers.ids import parse_path_id
from app.schemas.errors import (
    Error,
    JoinMatchBadRequest,
    JoinMatchConflict,
    JoinMatchForbidden,
    SubstitutionsConflict,
    ValidationBadRequest,
)
from app.schemas.match_connection import JoinMatchResponse
from app.schemas.substitution import Substitutions
from app.services.match_connection_service import MatchConnectionService
from app.services.substitution_service import SubstitutionService

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post(
    "/{match_id}/connections",
    response_model=JoinMatchResponse,
    status_code=201,
    operation_id="joinMatch",
    summary="Crear una conexión a un partido y obtener el token del WebSocket",
    responses={
        400: {"model": JoinMatchBadRequest},
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
    token = service.connect(user_id, parse_path_id(match_id, "El partido no existe."), body)
    return JoinMatchResponse(token_ws=token)


@router.get(
    "/{match_id}/substitutions",
    response_model=Substitutions,
    operation_id="getMatchSubstitutions",
    summary="Obtener la sustitución pedida de cada equipo de un partido en juego",
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
    operation_id="requestMatchSubstitution",
    summary="Pedir una sustitución para el equipo del usuario",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": SubstitutionsConflict},
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
                            "substituteId": {"type": "integer", "minimum": 1, "maximum": 2147483647},
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
    service.request_substitution(
        user_id, parse_path_id(match_id, "El partido no existe."), body
    )
    return Response(status_code=204)
