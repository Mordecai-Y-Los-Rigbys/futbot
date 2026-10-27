import json

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.helpers.ids import parse_path_id
from app.repositories.league_access_sqlalchemy import SqlAlchemyLeagueAccessRepository
from app.schemas.errors import Error
from app.schemas.league_access import UnlockLeagueBadRequest, UnlockLeagueForbidden
from app.services.league_access_service import LeagueAccessService

router = APIRouter(tags=["leagues"])


def get_league_access_service(db: Session = Depends(get_db)) -> LeagueAccessService:
    return LeagueAccessService(SqlAlchemyLeagueAccessRepository(db))


@router.post(
    "/{id}/access",
    status_code=204,
    response_class=Response,
    operation_id="unlockLeague",
    responses={
        400: {"model": UnlockLeagueBadRequest},
        401: {"model": Error},
        403: {"model": UnlockLeagueForbidden},
        404: {"model": Error},
    },
    openapi_extra={"requestBody": {
        "required": False,
        "content": {"application/json": {"schema": {
            "type": "object",
            "required": ["password"],
            "properties": {"password": {"type": "string", "nullable": True}},
        }}},
    }},
)
async def unlock_league(
    id: str,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    service: LeagueAccessService = Depends(get_league_access_service),
) -> Response:
    # Request sin Body/Pydantic: FastAPI no puede validar JSON antes del 401/404.
    league = service.get_league(parse_path_id(id, "La liga no existe."))
    session_id = request.cookies["session_id"]  # ya validada por get_current_user_id
    body = None
    if service.requires_password(session_id, user_id, league):
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # body ilegible -> password required
    service.unlock(session_id, user_id, league, body)
    return Response(status_code=204)
