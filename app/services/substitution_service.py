from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    FirstSubstitutionData,
)
from app.schemas.substitution import NextSubstitutions, SubstitutionResponse


def _to_response(item: FirstSubstitutionData | None) -> SubstitutionResponse | None:
    if item is None:
        return None
    return SubstitutionResponse(
        starter_name=item.starter_name, substitute_name=item.substitute_name
    )


class SubstitutionService:
    """Consulta de las sustituciones de un partido."""

    def __init__(
        self, matches: AbstractMatchRepository, substitutions: AbstractSubstitutionRepository
    ) -> None:
        self.matches = matches
        self.substitutions = substitutions

    def get_next(self, user_id: int, match_id: int) -> NextSubstitutions:
        """Primera sustitución de cada equipo. Orden: 404 > 403 > 409.

        Raises:
            ApiError 404: el partido no existe.
            ApiError 403: el usuario no es uno de los dos jugadores.
            ApiError 409: matchNotStarted, el partido no está `started`.
        """
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")
        if user_id not in (match.user_1_id, match.user_2_id):
            raise ApiError(403, None, "El partido no te pertenece.")
        if match.status != MatchStatus.started:
            raise ApiError(409, "matchNotStarted", "El partido no está en juego.")

        by_user = {i.user_id: i for i in self.substitutions.list_first_per_team(match_id)}
        return NextSubstitutions(
            club1=_to_response(by_user.get(match.user_1_id)),
            club2=_to_response(by_user.get(match.user_2_id)),
        )