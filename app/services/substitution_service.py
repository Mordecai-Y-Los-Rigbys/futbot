from sqlalchemy.exc import IntegrityError

from app.domain.match import MatchStatus
from app.errors import ApiError, ValidationApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.substitution_abstract import AbstractSubstitutionRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.schemas.substitution import Substitution, Substitutions
from app.services.match_progress import MatchProgressReader
from app.services.substitution_validation import parse_substitute
from app.simulation.match_rules import Phase

CHECK_VIOLATION = "23514"


def _to_response(item):
    if item is None:
        return None
    return Substitution(starter_name=item.starter_name, substitute_name=item.substitute_name)


class SubstitutionService:
    """Consulta y registro de las sustituciones de cada equipo."""

    def __init__(
        self,
        matches: AbstractMatchRepository,
        teams: AbstractTeamRepository,
        substitutions: AbstractSubstitutionRepository,
        progress: MatchProgressReader,
    ) -> None:
        self.matches = matches
        self.teams = teams
        self.substitutions = substitutions
        self.progress = progress

    def _ensure_substitutable(self, match, match_id: int, *, for_request: bool = False):
        """409 en este orden: matchNotStarted > matchInPenalties > noPausesLeft.

        `noPausesLeft` es `pauses_left == 0`, el mismo valor que viaja como
        `pausesLeft` en el tick (no cuenta la pausa en curso): una sola regla,
        sin recalcularla acá. El GET (`for_request=False`) dentro de una pausa
        siempre pasa: tiene que mostrar lo aplicado, incluso en la última. El PUT necesita una pausa por empezar donde aplicar el cambio, y
        un partido que no se juega en este proceso no la tiene: nadie lo aplicaría.

        Devuelve el progreso del partido (None si no se juega en este proceso).
        """
        if match.status != MatchStatus.started:
            raise ApiError(409, "matchNotStarted", "El partido no está en juego.")

        progress = self.progress.progress(match_id)
        if progress is None:
            if for_request:
                raise ApiError(409, "noPausesLeft", "Ya no quedan pausas en el partido.")
            return None

        paused = progress.phase is Phase.PAUSED
        if progress.in_penalties:
            raise ApiError(409, "matchInPenalties", "El partido está en la tanda de penales.")

        if progress.pauses_left == 0 and not (paused and not for_request):
            raise ApiError(409, "noPausesLeft", "Ya no quedan pausas en el partido.")
        return progress

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
        progress = self._ensure_substitutable(match, match_id)

        # progress None: el partido no se juega en este proceso. No sabemos la fase,
        # así que se responde la pendiente y no se evalúa noPausesLeft.
        paused = progress is not None and progress.phase is Phase.PAUSED
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
        # 404 antes de validar el body; el router ya resolvió 401 e id de ruta.
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")

        request, errors = parse_substitute(body)

        # Las reglas notStarter/notSubstitute dependen de un solo campo cada
        # una y solo existen para un usuario que efectivamente juega el partido.
        is_player = user_id in (match.user_1_id, match.user_2_id)
        starter_member_id = None
        substitute_member_id = None

        if is_player:
            if request.starter_id is not None:
                starters = self.teams.get_team_player_ids(
                    match_id, match.league_id, user_id, substitutes=False
                )
                if request.starter_id not in starters:
                    errors.append({"field": "starterId", "reason": "notStarter"})
                else:
                    starter_member_id = self.teams.get_member_id(
                        match_id, match.league_id, user_id, request.starter_id
                    )

            if request.substitute_id is not None:
                substitutes = self.teams.get_team_player_ids(
                    match_id, match.league_id, user_id, substitutes=True
                )
                if request.substitute_id not in substitutes:
                    errors.append({"field": "substituteId", "reason": "notSubstitute"})
                else:
                    substitute_member_id = self.teams.get_member_id(
                        match_id, match.league_id, user_id, request.substitute_id
                    )

        # El contrato exige el orden del schema: starterId, substituteId.
        field_order = {"starterId": 0, "substituteId": 1}
        errors.sort(key=lambda item: field_order[item["field"]])
        if errors:
            raise ValidationApiError(errors)

        if not is_player:
            raise ApiError(403, None, "El usuario no juega este partido.")

        self._ensure_substitutable(match, match_id, for_request=True)

        try:
            self.substitutions.upsert(
                match_id, user_id, substitute_member_id, starter_member_id
            )
        except IntegrityError as exc:
            if getattr(exc.orig, "pgcode", None) != CHECK_VIOLATION:
                raise
            # La alineación cambió (empezó una pausa) o el partido terminó entre
            # la validación y la escritura: se resuelve como lo haría una
            # revalidación.
            fresh = self.matches.get_players(match_id)
            if fresh is None or fresh.status != MatchStatus.started:
                raise ApiError(409, "matchNotStarted", "El partido no está en juego.")
            raise ValidationApiError(
                [
                    {"field": "starterId", "reason": "notStarter"},
                    {"field": "substituteId", "reason": "notSubstitute"},
                ]
            )
