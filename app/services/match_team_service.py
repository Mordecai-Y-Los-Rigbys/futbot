from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository
from app.repositories.team_abstract import AbstractTeamRepository, TeamBehaviorData
from app.schemas.match_team import MatchTeam, MatchTeamMember, TeamBehavior


def _behavior(data: TeamBehaviorData) -> TeamBehavior:
    return TeamBehavior(id=data.id, name=data.name, type=data.type)


class MatchTeamService:
    """Equipo del usuario en un partido (GET /matches/{id}/team)."""

    def __init__(self, matches: AbstractMatchRepository, teams: AbstractTeamRepository) -> None:
        self.matches = matches
        self.teams = teams

    def get_team(self, user_id: int, match_id: int) -> MatchTeam:
        """404 si el partido no existe; 403 `notAPlayerInMatch` si el usuario no
        es uno de sus dos clubes (también un espectador de un partido de liga).
        No hay 409: no depende del estado del partido. Solo devuelve el equipo
        del propio usuario, nunca el del rival."""
        match = self.matches.get_players(match_id)
        if match is None:
            raise ApiError(404, None, "El partido no existe.")
        # user_2_id puede ser None (amistoso sin rival): el creador sí pasa.
        if user_id not in (match.user_1_id, match.user_2_id):
            raise ApiError(403, "notAPlayerInMatch", "No sos jugador de este partido.")

        team = self.teams.get_match_team(match_id, match.league_id, user_id)
        return MatchTeam(
            members=[
                MatchTeamMember(
                    player_id=member.player_id,
                    name=member.name,
                    role=member.role,
                    behavior=_behavior(member.behavior),
                )
                for member in team.members
            ],
            coach_behavior=_behavior(team.coach_behavior) if team.coach_behavior else None,
        )
