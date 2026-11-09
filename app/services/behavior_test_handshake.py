from dataclasses import dataclass
from datetime import datetime, timezone

from app.errors import ApiError
from app.repositories.behavior_test_lineup_abstract import AbstractBehaviorTestLineupRepository
from app.repositories.behavior_test_token_abstract import AbstractBehaviorTestTokenRepository
from app.repositories.team_abstract import StarterData
from app.services.match_handshake_service import MAX_TOKEN_LEN


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BehaviorTestGrant:
    """Usuario y clubes de un handshake aceptado."""

    user_id: int
    behavior_id: int
    club_1: list[StarterData]
    club_2: list[StarterData]


class BehaviorTestHandshakeService:
    """Valida el handshake de /ws/behaviors/{id}/test y arma los dos clubes.

    El límite de una prueba por usuario (429) no vive acá: depende de las
    pruebas abiertas en memoria (ver BehaviorTestSlots).
    """

    def __init__(
        self,
        tokens: AbstractBehaviorTestTokenRepository,
        lineups: AbstractBehaviorTestLineupRepository,
    ) -> None:
        self.tokens = tokens
        self.lineups = lineups

    def authorize(self, token: str | None, raw_behavior_id: str) -> BehaviorTestGrant:
        """Valida el token y arma los clubes con la alineación guardada.

        Args:
            token: tokenWs de la query. Puede faltar.
            raw_behavior_id: id de la ruta, todavía sin validar.

        Raises:
            ApiError 401: tokenInvalid o tokenExpired.
            ApiError 403: tokenBehaviorMismatch (el token es de otro behavior).
            ApiError 404: behaviorNotFound (el de la URL o alguno de la alineación).
        """
        if not token or len(token) > MAX_TOKEN_LEN:
            raise ApiError(401, "tokenInvalid", "Token inválido.")
        record = self.tokens.get_by_token(token)
        if record is None:
            raise ApiError(401, "tokenInvalid", "Token inválido.")
        if record.expires_at <= _utcnow():
            raise ApiError(401, "tokenExpired", "El token expiró.")

        # Un id con otro formato ("05", "abc") tampoco es el del token.
        if raw_behavior_id != str(record.behavior_id):
            raise ApiError(
                403, "tokenBehaviorMismatch", "El token no corresponde a este comportamiento."
            )

        behavior_ids = {record.behavior_id} | {member.behavior_id for member in record.members}
        codes = self.lineups.behavior_codes(record.user_id, behavior_ids)
        if len(codes) != len(behavior_ids):
            raise ApiError(404, "behaviorNotFound", "Comportamiento no encontrado.")

        # Los jugadores no se pueden borrar: siguen estando desde el POST.
        players = self.lineups.players(record.user_id, [m.player_id for m in record.members])
        clubs: dict[str, list[StarterData]] = {"club1": [], "club2": []}
        for member in record.members:
            player = players[member.player_id]
            clubs[member.club].append(
                StarterData(
                    player_id=player.id,
                    name=player.name,
                    role=member.role,
                    power=player.power,
                    agility=player.agility,
                    control=player.control,
                    strength=player.strength,
                    speed=player.speed,
                    behavior_code=codes[member.behavior_id],
                )
            )
        return BehaviorTestGrant(
            user_id=record.user_id,
            behavior_id=record.behavior_id,
            club_1=clubs["club1"],
            club_2=clubs["club2"],
        )
