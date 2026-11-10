from app.domain.match import MatchStatus
from app.errors import ApiError, ValidationApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    SubstitutionData,
)
from app.repositories.team_abstract import AbstractTeamRepository
from app.schemas.substitution import Substitution, Substitutions
from app.services.field_validation import field_error
from app.services.match_progress import MatchProgressReader
from app.services.substitution_validation import parse_substitute
from app.simulation.match_rules import Phase


def _to_response(item: SubstitutionData | None) -> Substitution | None:
    if item is None:
        return None
    return Substitution(starter_name=item.starter_name, substitute_name=item.substitute_name)


class SubstitutionService:
    """Consulta y pedido de las sustituciones de un partido."""

    def __init__(
        self,
        matches: AbstractMatchRepository,
        substitutions: AbstractSubstitutionRepository,
        progress: MatchProgressReader,
        teams: AbstractTeamRepository,
    ) -> None:
        self.matches = matches
        self.substitutions = substitutions
        self.progress = progress
        self.teams = teams

    def get_substitutions(self, user_id: int, match_id: int) -> Substitutions:
        """Sustitución de cada equipo: la APLICADA si el partido está en pausa, la
        PENDIENTE (la que se aplica en la próxima pausa) si no lo está.

        Orden: 404 > 403 > 409, y dentro del 409:
        matchNotStarted > matchInPenalties > noPausesLeft.

        Raises:
            ApiError 404: el partido no existe.
            ApiError 403: el usuario no es uno de los dos jugadores.
            ApiError 409: matchNotStarted (el partido no está `started`),
                matchInPenalties (tanda de penales) o noPausesLeft (`pausesLeft` en 0
                y fuera de una pausa: no puede haber una pendiente; durante la última
                pausa se responde 200 con la aplicada).
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
            if progress.phase is Phase.PENALTIES:
                raise ApiError(409, "matchInPenalties", "El partido está en la tanda de penales.")
            if not paused and progress.pauses_left == 0:
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

    def request_substitution(self, user_id: int, match_id: int, body: object) -> None:
        """Guarda la sustitución pendiente del equipo del usuario (reemplaza la anterior).

        Orden: 404 > 400 > 403 > 409, y dentro del 409:
        matchNotStarted > matchInPenalties > noPausesLeft.

        Raises:
            ApiError 404: el partido no existe.
            ValidationApiError: invalidFields. notStarter y notSubstitute solo se
                evalúan si el usuario es jugador del partido.
            ApiError 403: el usuario no es uno de los dos jugadores.
            ApiError 409: matchNotStarted (el partido no está `started`),
                matchInPenalties (tanda de penales) o noPausesLeft (`pausesLeft` en 0,
                o el partido no se juega en este proceso).
        """
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")

        request, errors = parse_substitute(body)

        # notStarter y notSubstitute dependen de un solo campo cada una, y solo
        # existen para un usuario que juega el partido.
        is_player = user_id in (match.user_1_id, match.user_2_id)
        starter_member_id = None
        substitute_member_id = None

        if is_player:
            if request.starter_id is not None:
                starter_member_id = self.teams.get_member_id(
                    match_id, match.league_id, user_id, request.starter_id, substitute=False
                )
                if starter_member_id is None:
                    errors.append(field_error("starterId", "notStarter"))

            if request.substitute_id is not None:
                substitute_member_id = self.teams.get_member_id(
                    match_id, match.league_id, user_id, request.substitute_id, substitute=True
                )
                if substitute_member_id is None:
                    errors.append(field_error("substituteId", "notSubstitute"))

        # El contrato exige el orden del schema: starterId, substituteId.
        field_order = {"starterId": 0, "substituteId": 1}
        errors.sort(key=lambda item: field_order[item["field"]])
        if errors:
            raise ValidationApiError(errors)

        if not is_player:
            raise ApiError(403, None, "El usuario no juega este partido.")

        if match.status != MatchStatus.started:
            raise ApiError(409, "matchNotStarted", "El partido no está en juego.")

        # None: el partido no se juega en este proceso, así que nadie aplicaría el cambio.
        progress = self.progress.progress(match_id)
        if progress is not None and progress.phase is Phase.PENALTIES:
            raise ApiError(409, "matchInPenalties", "El partido está en la tanda de penales.")
        if progress is None or progress.pauses_left == 0:
            raise ApiError(409, "noPausesLeft", "Ya no quedan pausas en el partido.")

        self.substitutions.upsert(match_id, user_id, substitute_member_id, starter_member_id)
