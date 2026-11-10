import re

from app.domain.team_member import MemberRole
from app.errors import ApiError, ValidationApiError
from app.helpers.ids import MAX_ID
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.schemas.match_behavior import MatchPlayerBehavior
from app.services.field_validation import field_error

_INT_RE = re.compile(r"-?[0-9]+")


def parse_player_id(raw: str | None) -> int:
    """`playerId` de la query (convención 4: es dato de entrada, no el recurso de la ruta).

    Raises:
        ValidationApiError 400: `required` si falta o viene vacío, `invalidType` si no es
            un entero (`abc`, `1.5`), `outOfRange` si queda fuera de 1..MAX_ID.
    """
    if raw is None or raw == "":
        reason = "required"
    elif not _INT_RE.fullmatch(raw):
        reason = "invalidType"
    else:
        digits = raw.lstrip("-").lstrip("0")
        # El largo se mira antes de int()
        if raw.startswith("-") or digits == "" or len(digits) > len(str(MAX_ID)):
            reason = "outOfRange"
        elif int(digits) > MAX_ID:
            reason = "outOfRange"
        else:
            return int(digits)
    raise ValidationApiError([field_error("playerId", reason)])


class MatchPlayerBehaviorService:
    """Behavior (nombre y código) de un titular propio (GET /matches/{id}/behavior)."""

    def __init__(
        self,
        matches: AbstractMatchRepository,
        teams: AbstractTeamRepository,
        behaviors: AbstractBehaviorRepository,
    ) -> None:
        self.matches = matches
        self.teams = teams
        self.behaviors = behaviors

    def get_behavior(
        self, user_id: int, match_id: int, raw_player_id: str | None
    ) -> MatchPlayerBehavior:
        """Orden: 404 > 400 > 403 (el 401 lo resuelve la ruta). No hay 409.

        Entre los dos 403 se informa primero `notAPlayerInMatch`: un no-jugador
        no tiene equipo contra el cual evaluar `playerNotStarter`. No depende del
        estado del partido ni modifica nada.
        """
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")

        player_id = parse_player_id(raw_player_id)

        # user_2_id puede ser None (amistoso sin rival): el creador sí pasa.
        if user_id not in (match.user_1_id, match.user_2_id):
            raise ApiError(403, "notAPlayerInMatch", "No sos jugador de este partido.")

        # Misma alineación efectiva que GET /matches/{id}/team. Un suplente, un
        # jugador del rival o un id inexistente dan el mismo 403 (no revela ids).
        team = self.teams.get_match_team(match.id, match.league_id, user_id)
        starters = (m for m in team.members if m.role != MemberRole.substitute)
        starter = next((m for m in starters if m.player_id == player_id), None)
        if starter is None:
            raise ApiError(403, "playerNotStarter", "El jugador no es titular de tu equipo.")

        behavior = self.behaviors.get_by_id(starter.behavior.id)
        if behavior is None:  # no debería pasar: un behavior en un equipo no se puede borrar
            raise ApiError(404, None, "El behavior no existe.")
        return MatchPlayerBehavior(name=behavior.name, code=behavior.code)
