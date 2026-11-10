from abc import ABC, abstractmethod
from pydantic import BaseModel
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
    def get_team_player_ids(
        self, match_id: int, league_id: int | None, user_id: int, *, substitutes: bool
    ) -> set[int]:
        """IDs de jugadores titulares o suplentes de la alineación efectiva actual."""

    @abstractmethod
    def get_member_id(
        self, match_id: int, league_id: int | None, user_id: int, player_id: int
    ) -> int | None:
        """ID de la fila team_members que representa al jugador en el equipo."""
