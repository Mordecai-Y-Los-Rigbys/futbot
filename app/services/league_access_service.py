import hashlib
import hmac
from typing import Any

from fastapi.responses import JSONResponse

from app.errors import ApiError
from app.repositories.league_access_abstract import LeagueAccessInfo, LeagueAccessRepository


class LeagueAccessValidationError(ApiError):
    def __init__(self, reason: str) -> None:
        super().__init__(400, "invalidFields", "La contraseña no cumple el formato requerido.")
        self.reason = reason

    def to_response(self) -> JSONResponse:
        return JSONResponse(status_code=400, content={
            "code": self.code,
            "message": self.message,
            "errors": [{"field": "password", "reason": self.reason}],
        })


def has_league_access(
    session_id: str,
    user_id: int,
    league: LeagueAccessInfo,
    repository: LeagueAccessRepository,
) -> bool:
    """Regla compartida REST/WS. Requiere una sesión vigente del user_id indicado.

    La autenticación debe ejecutarse antes de esta regla, también en WebSocket.
    No registra desbloqueos: consultar acceso no equivale a llamar a /access.
    """
    return (
        not league.private
        or league.creator_id == user_id
        or repository.is_participant(league.id, user_id)
        or repository.is_unlocked(session_id, league.id)
    )


def verify_league_password(received: str, expected: str) -> bool:
    # Se comparan digests de igual longitud. Soporta Unicode sin normalizar,
    # recortar ni cambiar la contraseña que actualmente guarda League.
    return hmac.compare_digest(
        hashlib.sha256(received.encode("utf-8", errors="surrogatepass")).digest(),
        hashlib.sha256(expected.encode("utf-8", errors="surrogatepass")).digest(),
    )


class LeagueAccessService:
    def __init__(self, repository: LeagueAccessRepository) -> None:
        self.repository = repository

    def get_league(self, league_id: int) -> LeagueAccessInfo:
        league = self.repository.get_league(league_id)
        if league is None:
            raise ApiError(404, None, "La liga no existe.")
        return league

    def requires_password(self, session_id: str, user_id: int, league: LeagueAccessInfo) -> bool:
        return not has_league_access(session_id, user_id, league, self.repository)

    def unlock(
        self, session_id: str, user_id: int, league: LeagueAccessInfo, body: Any
    ) -> None:
        if not league.private:
            return
        if self.requires_password(session_id, user_id, league):
            password = body.get("password") if isinstance(body, dict) else None
            if password is None:
                raise LeagueAccessValidationError("required")
            if not isinstance(password, str):
                raise LeagueAccessValidationError("invalidType")
            matches = verify_league_password(password, league.password or "")
            if not password or league.password is None or not matches:
                raise ApiError(403, "invalidLeaguePassword", "Contraseña de liga incorrecta.")
        self.repository.unlock(session_id, league.id)

    def require_access(self, session_id: str, user_id: int, league: LeagueAccessInfo) -> None:
        """Para los GET protegidos: llamar después del 404 y antes de los 409."""
        if not has_league_access(session_id, user_id, league, self.repository):
            raise ApiError(403, "leagueAccessRequired", "Debés desbloquear esta liga.")
