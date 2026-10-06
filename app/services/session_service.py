import secrets
from datetime import datetime, timedelta, timezone

from app.repositories.session_abstract import (
    AbstractSessionRepository,
    CreateSessionData,
    SessionData,
)

SESSION_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    """Crea, valida y borra las sesiones de los usuarios."""

    def __init__(self, repository: AbstractSessionRepository) -> None:
        self.repository = repository

    def create(self, user_id: int, ttl: timedelta = SESSION_TTL) -> SessionData:
        """Crea una sesión. El valor de la cookie es `session.id`."""
        now = _utcnow()
        return self.repository.create(
            CreateSessionData(
                id=secrets.token_urlsafe(32),  # 43 caracteres, entra en String(64)
                user_id=user_id,
                created_at=now,
                expires_at=now + ttl,
            )
        )

    def get_user_id(self, session_id: str) -> int | None:
        """Devuelve el user_id si la sesión existe y no expiró; si no, None."""
        session = self.repository.get_by_id(session_id)
        if session is None:
            return None

        if session.expires_at <= _utcnow():
            self.repository.delete(session_id)  # limpieza de sesiones vencidas
            return None

        return session.user_id

    def delete(self, session_id: str) -> None:
        """Cierra la sesión (logout). No falla si no existe."""
        self.repository.delete(session_id)
