from datetime import timezone

from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.repositories.session_abstract import (
    AbstractSessionRepository,
    CreateSessionData,
    SessionData,
)


def _to_data(record: UserSession) -> SessionData:
    # Las columnas DateTime sin timezone vuelven "naive": es un detalle de
    # persistencia, así que se normaliza acá y el servicio siempre recibe
    # datetimes con timezone.
    created_at = record.created_at
    expires_at = record.expires_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return SessionData(
        id=record.id,
        user_id=record.user_id,
        created_at=created_at,
        expires_at=expires_at,
    )


class SqlAlchemySessionRepository(AbstractSessionRepository):
    def __init__(self, db: Session):
        self.db = db

    def create(self, session: CreateSessionData) -> SessionData:
        record = UserSession(**session.model_dump())
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return _to_data(record)

    def get_by_id(self, session_id: str) -> SessionData | None:
        record = self.db.get(UserSession, session_id)
        return _to_data(record) if record is not None else None

    def delete(self, session_id: str) -> None:
        record = self.db.get(UserSession, session_id)
        if record is not None:
            self.db.delete(record)
            self.db.commit()
