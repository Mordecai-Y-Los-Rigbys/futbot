import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

# Ajustá el nombre de la clase si en app/models/session.py se llama distinto.
from app.models.session import UserSession

SESSION_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, ttl: timedelta = SESSION_TTL) -> UserSession:
        """Crea una sesión. El valor de la cookie es `session.id`."""
        now = _utcnow()
        session = UserSession(
            id=secrets.token_urlsafe(32),  # 43 caracteres, entra en String(64)
            user_id=user_id,
            created_at=now,
            expires_at=now + ttl,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_user_id(self, session_id: str) -> int | None:
        """Devuelve el user_id si la sesión existe y no expiró; si no, None."""
        record = self.db.get(UserSession, session_id)
        if record is None:
            return None

        expires_at = record.expires_at
        if expires_at.tzinfo is None:  # columnas DateTime sin timezone vuelven "naive"
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= _utcnow():
            self.db.delete(record)  # limpieza de sesiones vencidas
            self.db.commit()
            return None

        return record.user_id

    def delete(self, session_id: str) -> None:
        """Cierra la sesión (logout). No falla si no existe."""
        record = self.db.get(UserSession, session_id)
        if record is not None:
            self.db.delete(record)
            self.db.commit()