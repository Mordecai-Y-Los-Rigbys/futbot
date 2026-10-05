import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.match_ws_token_abstract import AbstractMatchWsTokenRepository

MAX_TOKEN_LEN = 64  # largo de la columna: algo más largo no puede existir
_ID_RE = re.compile(r"[0-9]{1,10}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class HandshakeGrant:
    user_id: int
    match_id: int


class MatchHandshakeService:
    """Valida el handshake de /ws/matches/{id}. Lanza ApiError con el status
    HTTP con el que hay que rechazar el handshake (antes del upgrade).

    El límite de conexiones por usuario (429) no vive acá: depende del estado
    en memoria de las conexiones abiertas (ver MatchConnectionManager).
    """

    def __init__(
        self,
        tokens: AbstractMatchWsTokenRepository,
        matches: AbstractMatchRepository,
    ) -> None:
        self.tokens = tokens
        self.matches = matches

    def authorize(self, token: str | None, raw_match_id: str) -> HandshakeGrant:
        # 401: falta, es inválido o expiró
        if not token or len(token) > MAX_TOKEN_LEN:
            raise ApiError(401, "tokenInvalid", "Token inválido.")

        record = self.tokens.get_by_token(token)
        if record is None:
            raise ApiError(401, "tokenInvalid", "Token inválido.")
        if record.expires_at <= _utcnow():
            raise ApiError(401, "tokenExpired", "El token expiró.")

        if not _ID_RE.fullmatch(raw_match_id) or int(raw_match_id) != record.match_id:
            raise ApiError(403, "tokenMatchMismatch", "El token no corresponde a este partido.")

        match = self.matches.get_state(record.match_id)
        if match is None:
            raise ApiError(404, "matchNotFound", "Partido no encontrado.")
        if match.status == MatchStatus.finished:
            raise ApiError(409, "matchFinished", "El partido ya terminó.")
        if match.status == MatchStatus.cancelled:
            raise ApiError(409, "matchCancelled", "El partido fue cancelado.")

        return HandshakeGrant(user_id=record.user_id, match_id=record.match_id)
