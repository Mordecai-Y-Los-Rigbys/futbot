from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.helpers.ids import parse_path_id
from app.repositories.league_access_abstract import LeagueAccessRepository
from app.repositories.session_abstract import SessionData
from app.services.league_access_service import has_league_access

MAX_SESSION_ID_LEN = 64
LEAGUE_NOT_FOUND_MESSAGE = "La liga no existe."


class ValidSessions(Protocol):
    def get_valid(self, session_id: str) -> SessionData | None: ...


class LeagueStatusReader(Protocol):
    def get_status(self, league_id: int) -> LeagueStatus | None: ...


# Devuelve el 409 si el canal no admite la liga en ese estado; None si la admite.
RejectStatus = Callable[[LeagueStatus | None], ApiError | None]


def authorize_session(
    allowed_origins: Collection[str],
    sessions: ValidSessions,
    origin: str | None,
    session_id: str | None,
) -> SessionData:
    """Primeros pasos del handshake de los canales que usan la cookie de sesión.

    Raises:
        ApiError 403 originNotAllowed: falta el header Origin o no está permitido.
        ApiError 401 sessionInvalid: sin cookie o con una sesión inválida o vencida.
    """
    # El origen se valida antes que la sesión
    if not origin or origin not in allowed_origins:
        raise ApiError(403, "originNotAllowed", "Origen no permitido.")

    session = None
    if session_id and len(session_id) <= MAX_SESSION_ID_LEN:
        session = sessions.get_valid(session_id)
    if session is None:
        raise ApiError(401, "sessionInvalid", "Sin sesión válida.")
    return session


@dataclass(frozen=True)
class LeagueChannelGrant:
    """Usuario, liga y sesión de un handshake aceptado."""

    user_id: int
    league_id: int
    session_id: str
    session_expires_at: datetime


class LeagueChannelHandshakeService:
    """Valida el handshake de un canal /ws/leagues/{id}/...

    El límite de conexiones (429) no vive acá: lo aplica el manager.
    """

    def __init__(
        self,
        allowed_origins: Collection[str],
        sessions: ValidSessions,
        access: LeagueAccessRepository,
        statuses: LeagueStatusReader,
        reject_status: RejectStatus,
    ) -> None:
        self.allowed_origins = set(allowed_origins)
        self.sessions = sessions
        self.access = access
        self.statuses = statuses
        self._reject_status = reject_status

    def authorize(
        self, origin: str | None, session_id: str | None, raw_league_id: str
    ) -> LeagueChannelGrant:
        """Valida una conexión. Lanza solo la primera falla, en este orden:

        Raises:
            ApiError 403 originNotAllowed: falta el header Origin o no está permitido.
            ApiError 401 sessionInvalid: sin cookie o con una sesión inválida o vencida.
            ApiError 404 leagueNotFound: id inválido o liga inexistente.
            ApiError 403 leagueAccessRequired: liga privada sin acceso (convención 11).
            ApiError 409: la liga no está en un estado que el canal admita.
        """
        session = authorize_session(self.allowed_origins, self.sessions, origin, session_id)

        # 404
        try:
            league_id = parse_path_id(raw_league_id, LEAGUE_NOT_FOUND_MESSAGE)
        except ApiError:
            raise ApiError(404, "leagueNotFound", LEAGUE_NOT_FOUND_MESSAGE) from None
        league = self.access.get_league(league_id)
        if league is None:
            raise ApiError(404, "leagueNotFound", LEAGUE_NOT_FOUND_MESSAGE)

        # 403: convención 11
        if not has_league_access(session.id, session.user_id, league, self.access):
            raise ApiError(403, "leagueAccessRequired", "Debés desbloquear esta liga.")

        # 409
        error = self._reject_status(self.statuses.get_status(league_id))
        if error is not None:
            raise error

        return LeagueChannelGrant(
            user_id=session.user_id,
            league_id=league_id,
            session_id=session.id,
            session_expires_at=session.expires_at,
        )
