import json
from typing import Any

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository
from app.repositories.match_connection_sqlalchemy import SqlAlchemyMatchConnectionRepository
from app.repositories.player_sqlalchemy import SqlAlchemyPlayerRepository
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.repositories.league_abstract import AbstractLeagueRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository
from app.repositories.friendly_sqlalchemy import SqlAlchemyFriendlyRepository
from app.repositories.match_connection_sqlalchemy import SqlAlchemyMatchConnectionRepository
from app.repositories.user_sqlalchemy import SqlAlchemyUserRepository
from app.services.auth_service import AuthService
from app.services.player_service import PlayerService
from app.services.behavior_service import BehaviorService
from app.services.league_service import LeagueService
from app.services.league_validation import INVALID_JSON
from app.services.session_service import SessionService
from app.services.friendly_service import FriendlyService
from app.services.match_connection_service import MatchConnectionService
from app.services.user_service import UserService



def get_league_repository(db=Depends(get_db)) -> AbstractLeagueRepository:
    return SqlAlchemyLeagueRepository(db)

def get_team_repository(db=Depends(get_db)) -> AbstractTeamRepository:
    return SqlAlchemyTeamRepository(db)


def get_behavior_service(db: Session = Depends(get_db)) -> BehaviorService:
    return BehaviorService(SqlAlchemyBehaviorRepository(db))


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    return SessionService(SqlAlchemySessionRepository(db))

def get_league_service(
    leagues=Depends(get_league_repository),
    teams=Depends(get_team_repository),
) -> LeagueService:
    return LeagueService(leagues, teams)

def get_player_service(db: Session = Depends(get_db)) -> PlayerService:
    return PlayerService(SqlAlchemyPlayerRepository(db))

def get_auth_service(
    db: Session = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
    behavior_service: BehaviorService = Depends(get_behavior_service),
) -> AuthService:
    user_repo = SqlAlchemyUserRepository(db)
    return AuthService(
        user_repo=user_repo,
        session_service=session_service,
        behavior_service=behavior_service,
    )


def get_current_user_id(
    session_id: str | None = Cookie(default=None),
    service: SessionService = Depends(get_session_service),
) -> int:
    """
    Devuelve el user_id de la sesión actual. Lanza 401 (code: null) si no hay
    cookie, la sesión no existe o expiró. El 401 se reserva EXCLUSIVAMENTE
    a "sin sesión válida" (ver convenciones del YAML).
    """
    if not session_id:
        raise ApiError(401, None, "Sin sesión válida.")

    user_id = service.get_user_id(session_id)
    if user_id is None:
        raise ApiError(401, None, "Sin sesión válida.")

    return user_id


async def get_json_body(
    request: Request,
    _user_id: int = Depends(get_current_user_id),  # 401 antes de tocar el body
) -> Any:
    """
    Devuelve el body JSON crudo (sin validar). None si viene vacío,
    INVALID_JSON si no se pudo parsear. Las validaciones y sus códigos
    viven en el service (convención 6 de la API Rest).
    """
    raw = await request.body()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return INVALID_JSON


def get_friendly_service(db: Session = Depends(get_db)) -> FriendlyService:
    return FriendlyService(SqlAlchemyFriendlyRepository(db))

def get_match_connection_service(db: Session = Depends(get_db)) -> MatchConnectionService:
    return MatchConnectionService(SqlAlchemyMatchConnectionRepository(db))

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(SqlAlchemyUserRepository(db))