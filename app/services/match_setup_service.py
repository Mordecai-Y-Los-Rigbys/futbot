"""Arma los equipos de un partido a partir de los repositories.

El service decide y valida; los repositories solo traen datos planos.
"""

from dataclasses import dataclass

from app.repositories.league_abstract import AbstractLeagueRepository
from app.repositories.match_abstract import AbstractMatchRepository, MatchSetupData
from app.repositories.team_abstract import AbstractTeamRepository
from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.constants import (
    STARTER_ROLES,
    COUNTDOWN_SECONDS,
    FRIENDLY_MATCH_DURATION,
)
from app.simulation.match_rules import TeamSetup
from app.simulation.physics import PlayerSetup
from app.simulation.state import Stats


@dataclass(frozen=True)
class MatchSetup:
    team_1: TeamSetup  # club1 = user_1
    team_2: TeamSetup  # club2 = user_2
    duration_seconds: float
    countdown_seconds: float
    club_1_name: str
    club_2_name: str

class MatchSetupService:
    def __init__(
        self,
        matches: AbstractMatchRepository,
        leagues: AbstractLeagueRepository,
        teams: AbstractTeamRepository,
    ):
        self.matches = matches
        self.leagues = leagues
        self.teams = teams

    def load_match_setup(self, match_id: int) -> MatchSetup:
        match = self.matches.get_setup_data(match_id)
        if match is None or match.user_2_id is None or match.club_2_name is None:
            raise LookupError(f"partido {match_id} inexistente o sin rival")

        minutes = self._duration_minutes(match)

        return MatchSetup(
            team_1=self._build_team(match, match.user_1_id),
            team_2=self._build_team(match, match.user_2_id),
            duration_seconds=minutes * 60,
            countdown_seconds=COUNTDOWN_SECONDS,
            club_1_name=match.club_1_name,
            club_2_name=match.club_2_name,
        )

    def _duration_minutes(self, match: MatchSetupData) -> int:
        # Amistoso: duración fija. Partido de liga: la que definió la liga.
        if match.league_id is None:
            return FRIENDLY_MATCH_DURATION

        minutes = self.leagues.get_match_duration_minutes(match.league_id)
        if minutes is None:
            raise LookupError(
                f"la liga {match.league_id} del partido {match.id} no existe"
            )
        return minutes

    def _build_team(self, match: MatchSetupData, user_id: int) -> TeamSetup:
        # El repo ya resuelve de dónde sale el equipo (liga o partido) y
        # devuelve solo los titulares.
        rows = self.teams.get_starters(match.id, match.league_id, user_id)

        players: list[PlayerSetup] = []
        behaviors = {}
        for row in rows:
            role = row.role
            if role not in STARTER_ROLES:
                raise ValueError(
                    f"el usuario {user_id} tiene un {role.value} entre los "
                    f"titulares del partido {match.id}"
                )
            if role in behaviors:
                raise ValueError(
                    f"el usuario {user_id} tiene el rol {role.value} repetido "
                    f"en el partido {match.id}"
                )
            stats = Stats(
                power=row.power,
                agility=row.agility,
                control=row.control,
                strength=row.strength,
                speed=row.speed,
            )
            players.append(PlayerSetup(row.player_id, role, stats))
            behaviors[role] = compile_behavior(row.behavior_code)

        if len(players) != len(STARTER_ROLES):
            raise ValueError(
                f"el usuario {user_id} no tiene {len(STARTER_ROLES)} titulares "
                f"en el partido {match.id}"
            )
        return TeamSetup(players=players, behaviors=behaviors)