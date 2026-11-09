from typing import Any, Protocol

from app.domain.behavior import BehaviorType
from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.services.match_behavior_validation import parse_reassign_behavior
from app.simulation.behaviors.sandbox import CompiledBehavior, compile_behavior


class BehaviorQueue(Protocol):
    """Lo que el service necesita del runner (lo cumple MatchRunner)."""

    def is_running(self, match_id: int) -> bool: ...

    def queue_behavior(self, match_id: int, player_id: int, behavior: CompiledBehavior) -> bool: ...


def _not_in_progress() -> ApiError:
    return ApiError(409, "matchNotInProgress", "El partido no está en juego.")


class MatchBehaviorService:
    def __init__(
        self,
        matches: AbstractMatchRepository,
        teams: AbstractTeamRepository,
        behaviors: AbstractBehaviorRepository,
        runner: BehaviorQueue,
    ) -> None:
        self.matches = matches
        self.teams = teams
        self.behaviors = behaviors
        self.runner = runner

    def reassign(self, user_id: int, match_id: int, body: Any) -> None:
        """Encola el cambio para el próximo tick y lo guarda en el equipo.

        Orden: 404 > 400 > 403 > 409, y dentro del 409:
        matchNotInProgress > playerOrBehaviorNotOwned > behaviorTypeMismatch.
        """
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")

        data = parse_reassign_behavior(body)

        if user_id not in (match.user_1_id, match.user_2_id):
            raise ApiError(403, "notAPlayerInMatch", "No sos jugador de este partido.")
        starters = self.teams.get_starters(match.id, match.league_id, user_id)
        if data.player_id not in {s.player_id for s in starters}:
            raise ApiError(403, "playerNotStarter", "El jugador no es titular de tu equipo.")

        if match.status != MatchStatus.started or not self.runner.is_running(match.id):
            raise _not_in_progress()

        kind = self.behaviors.behavior_types(user_id, [data.behavior_id]).get(data.behavior_id)
        if kind is None:
            raise ApiError(409, "playerOrBehaviorNotOwned", "El comportamiento no te pertenece.")
        if kind != BehaviorType.player_behavior:
            raise ApiError(
                409, "behaviorTypeMismatch", "Un jugador necesita un behavior de jugador."
            )

        code = self.behaviors.get_by_id(data.behavior_id).code
        if not self.runner.queue_behavior(match.id, data.player_id, compile_behavior(code)):
            raise _not_in_progress()

        self.teams.set_behavior(match_id, match.league_id, data.player_id, data.behavior_id)
