from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    SubstitutionData,
)
from app.schemas.substitution import Substitution, Substitutions
from app.services.match_progress import MatchProgressReader
from app.simulation.match_rules import Phase


def _to_response(item: SubstitutionData | None) -> Substitution | None:
    if item is None:
        return None
    return Substitution(starter_name=item.starter_name, substitute_name=item.substitute_name)


class SubstitutionService:
    """Consulta de las sustituciones de un partido."""

    def __init__(
        self,
        matches: AbstractMatchRepository,
        substitutions: AbstractSubstitutionRepository,
        progress: MatchProgressReader,
    ) -> None:
        self.matches = matches
        self.substitutions = substitutions
        self.progress = progress

    def get_substitutions(self, user_id: int, match_id: int) -> Substitutions:
        """Sustitución de cada equipo: la APLICADA si el partido está en pausa, la
        PENDIENTE (la que se aplica en la próxima pausa) si no lo está.

        Orden: 404 > 403 > 409, y dentro del 409:
        matchNotStarted > matchInPenalties > noPausesLeft.

        Raises:
            ApiError 404: el partido no existe.
            ApiError 403: el usuario no es uno de los dos jugadores.
            ApiError 409: matchNotStarted (el partido no está `started`),
                matchInPenalties (tanda de penales) o noPausesLeft (fuera de una
                pausa y en el último período: no puede haber una pendiente;
                durante la última pausa se responde 200 con la aplicada).
        """
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")
        if user_id not in (match.user_1_id, match.user_2_id):
            raise ApiError(403, None, "El partido no te pertenece.")
        if match.status != MatchStatus.started:
            raise ApiError(409, "matchNotStarted", "El partido no está en juego.")

        # None: el partido no se juega en este proceso. No sabemos la fase, así que
        # se responde la pendiente y no se evalúa noPausesLeft.
        progress = self.progress.progress(match_id)
        paused = progress is not None and progress.phase is Phase.PAUSED
        if progress is not None:
            if progress.in_penalties:
                raise ApiError(409, "matchInPenalties", "El partido está en la tanda de penales.")
            if not paused and progress.period >= progress.periods:
                raise ApiError(409, "noPausesLeft", "Ya no quedan pausas en el partido.")

        rows = (
            self.substitutions.list_applied_by_match(match_id)
            if paused
            else self.substitutions.list_by_match(match_id)
        )
        by_user = {i.user_id: i for i in rows}
        return Substitutions(
            club1=_to_response(by_user.get(match.user_1_id)),
            club2=_to_response(by_user.get(match.user_2_id)),
        )
