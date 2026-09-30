from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.services.session_service import SessionService
from app.services.behavior_service import BehaviorService
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository


def get_behavior_service(db: Session = Depends(get_db)) -> BehaviorService:
    return BehaviorService(SqlAlchemyBehaviorRepository(db))

def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    return SessionService(SqlAlchemySessionRepository(db))

def get_current_user_id(
    session_id: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> int:
    """
    Devuelve el user_id de la sesión actual. Lanza 401 (code: null) si no hay
    cookie, la sesión no existe o expiró. El 401 se reserva EXCLUSIVAMENTE
    a "sin sesión válida" (ver convenciones del YAML).
    """
    if not session_id:
        raise ApiError(401, None, "Sin sesión válida.")

    user_id = SessionService(db).get_user_id(session_id)
    if user_id is None:
        raise ApiError(401, None, "Sin sesión válida.")

    return user_id