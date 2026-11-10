from abc import ABC, abstractmethod
from pydantic import BaseModel
from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole


class StarterData(BaseModel):
    player_id: int
    name: str
    role: MemberRole
    power: int
    agility: int
    control: int
    strength: int
    speed: int
    behavior_code: str


class LineupPlayerData(BaseModel):
    player_id: int
    name: str
    role: MemberRole


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
    def get_starters(self, match_id: int, league_id: int | None, user_id: int) -> list[StarterData]:
        """Titulares del usuario: del equipo del partido (amistoso) o de la liga."""

    @abstractmethod
    def get_lineup(
        self, match_id: int, league_id: int | None, user_id: int
    ) -> list[LineupPlayerData]:
        """Id, nombre y rol de los titulares del usuario en el partido, sin orden.
        Con las sustituciones ya aplicadas, porque cambian el rol en el equipo."""

    @abstractmethod
    def set_behavior(
        self, match_id: int, league_id: int | None, player_id: int, behavior_id: int
    ) -> None:
        """Le asigna el comportamiento al jugador en su equipo: el de la liga o el del amistoso."""

    @abstractmethod
    def get_member_id(
        self,
        match_id: int,
        league_id: int | None,
        user_id: int,
        player_id: int,
        *,
        substitute: bool,
    ) -> int | None:
        """Fila de `team_members` del jugador en el equipo del usuario, si es suplente
        (`substitute=True`) o titular (`substitute=False`) en la alineación actual.
        None si no está en el equipo con ese rol."""

    @abstractmethod
    def get_match_team(self, match_id: int, league_id: int | None, user_id: int) -> MatchTeamData:
        """Equipo efectivo del usuario en el partido: titulares (forward,
        midfield, defense) y después suplentes, cada uno con su behavior actual,
        más el behavior del DT (None si el equipo no tiene).

        Es de solo lectura y no mira el estado del partido ni las sustituciones
        pendientes: solo lo que está guardado en `team_members`.
        """
