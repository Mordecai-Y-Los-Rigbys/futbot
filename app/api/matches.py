import re
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_user_id,
    get_json_body,
    get_match_connection_service,
)
from app.errors import ApiError
from app.schemas.errors import (
    Error,
    JoinMatchBadRequest,
    JoinMatchConflict,
    JoinMatchForbidden,
)
from app.schemas.match_connection import JoinMatchResponse
from app.services.match_connection_service import MatchConnectionService

router = APIRouter(prefix="/matches", tags=["matches"])

MAX_ID = 2147483647
_ID_RE = re.compile(r"[0-9]{1,10}")


def parse_match_id(raw: str) -> int:
    """Un id que no puede identificar ningún partido es un partido inexistente (404)."""
    if _ID_RE.fullmatch(raw):
        value = int(raw)
        if 1 <= value <= MAX_ID:
            return value
    raise ApiError(404, None, "El partido no existe.")


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
    token = service.connect(user_id, parse_match_id(match_id), body)
    return JoinMatchResponse(token_ws=token)