import secrets
from datetime import datetime, timezone
from typing import Any

from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_connection_abstract import (
    AbstractMatchConnectionRepository,
    CreateMatchWsTokenData,
    MatchAccessData,
)
from app.services.match_timing import WS_TOKEN_TTL


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchConnectionService:
    """Emite los tokens para conectarse al WebSocket de un partido."""

    def __init__(self, repo: AbstractMatchConnectionRepository) -> None:
        self.repo = repo

    def connect(self, user_id: int, match_id: int, body: Any) -> str:
        """Devuelve un tokenWs. Orden: 404 > 400 > 403 > 409."""
        match = self.repo.get_access(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")

        if self._password_applies(match, user_id):
            self._check_password(match, body)

        if match.status == MatchStatus.finished:
            raise ApiError(409, "matchFinished", "El partido ya terminó.")
        if match.status == MatchStatus.cancelled:
            raise ApiError(409, "matchCancelled", "El partido fue cancelado.")

        now = _utcnow()
        token = secrets.token_urlsafe(32)  # 43 chars, entra en String(64)
        self.repo.create_token(
            CreateMatchWsTokenData(
                token=token,
                user_id=user_id,
                match_id=match.id,
                created_at=now,
                expires_at=now + WS_TOKEN_TTL,
            )
        )
        return token

    def _password_applies(self, match: MatchAccessData, user_id: int) -> bool:
        """Solo se evalúa en liga privada y con un usuario ajeno a ella."""
        if match.league_id is None or not match.league_private:
            return False
        if match.league_creator_id == user_id:
            return False
        return not self.repo.is_league_participant(match.league_id, user_id)

    @staticmethod
    def _check_password(match: MatchAccessData, body: Any) -> None:
        password = body.get("password") if isinstance(body, dict) else None
        if password is not None and not isinstance(password, str):
            raise ApiError(400, "invalidFieldType", "La contraseña debe ser un string.")
        expected = (match.league_password or "").encode()
        if password is None or not secrets.compare_digest(password.encode(), expected):
            raise ApiError(403, "invalidLeaguePassword", "La contraseña de la liga es incorrecta.")
