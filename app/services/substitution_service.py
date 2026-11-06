from app.domain.match import MatchStatus
from app.errors import ApiError, ValidationApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.substitution_abstract import AbstractSubstitutionRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.schemas.substitution import Substitution, Substitutions
from app.services.substitution_validation import parse_substitute


def _to_response(item):
    if item is None:
        return None
    return Substitution(starter_name=item.starter_name, substitute_name=item.substitute_name)


class SubstitutionService:
    """Consulta y registro de la única sustitución pendiente de cada equipo."""

    def __init__(
        self,
        matches: AbstractMatchRepository,
        teams: AbstractTeamRepository,
        substitutions: AbstractSubstitutionRepository,
        runtime=None,
    ) -> None:
        self.matches = matches
        self.teams = teams
        self.substitutions = substitutions
        self.runtime = runtime

    def get_substitutions(self, user_id: int, match_id: int) -> Substitutions:
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")
        if user_id not in (match.user_1_id, match.user_2_id):
            raise ApiError(403, None, "El partido no te pertenece.")
        if match.status != MatchStatus.started:
            raise ApiError(409, "matchNotStarted", "El partido no está en juego.")

        by_user = {i.user_id: i for i in self.substitutions.list_by_match(match_id)}
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

        # Precedencia interna del 409: estado, tanda, pausas restantes.
        if match.status != MatchStatus.started:
            raise ApiError(409, "matchNotStarted", "El partido no está en juego.")

        runtime = self.runtime.get_runtime_state(match_id) if self.runtime else None
        if runtime is not None and runtime.in_penalties:
            raise ApiError(409, "matchInPenalties", "El partido está en tanda de penales.")
        if runtime is None or runtime.pauses_left <= 0:
            raise ApiError(409, "noPausesLeft", "El partido ya pasó su última pausa.")

        self.substitutions.upsert(
            match_id, user_id, substitute_member_id, starter_member_id
        )
