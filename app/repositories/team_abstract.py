from abc import ABC, abstractmethod
from pydantic import BaseModel
from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole


class StarterData(BaseModel):
    player_id: int
    role: MemberRole
    power: int
    agility: int
    control: int
    strength: int
    speed: int
    behavior_code: str


class TeamBehaviorData(BaseModel):
    id: int
    name: str
    type: BehaviorType


class TeamMemberData(BaseModel):
    player_id: int
    name: str
    role: MemberRole
    behavior: TeamBehaviorData


class MatchTeamData(BaseModel):
    members: list[TeamMemberData]
    coach_behavior: TeamBehaviorData | None


class AbstractTeamRepository(ABC):
    @abstractmethod
    def get_team_player_ids(
        self, match_id: int, league_id: int | None, user_id: int, *, substitutes: bool
    ) -> set[int]:
        """IDs de jugadores titulares o suplentes de la alineación efectiva actual."""

    @abstractmethod
    def get_member_id(
        self, match_id: int, league_id: int | None, user_id: int, player_id: int
    ) -> int | None:
        """ID de la fila team_members que representa al jugador en el equipo."""

    @abstractmethod
    def get_starters(
        self, match_id: int, league_id: int | None, user_id: int
    ) -> list[StarterData]:
        """Titulares del usuario: del equipo del partido (amistoso) o de la liga."""

    @abstractmethod
    def get_match_team(
        self, match_id: int, league_id: int | None, user_id: int
    ) -> MatchTeamData:
        """Equipo efectivo del usuario en el partido: titulares (forward,
        midfield, defense) y después suplentes, cada uno con su behavior actual,
        más el behavior del DT (None si el equipo no tiene).

        Es de solo lectura y no mira el estado del partido ni las sustituciones
        pendientes: solo lo que está guardado en `team_members`.
        """