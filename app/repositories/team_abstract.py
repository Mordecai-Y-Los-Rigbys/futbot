from abc import ABC, abstractmethod
from pydantic import BaseModel
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

class AbstractTeamRepository(ABC):
    @abstractmethod
    def get_starters(self, match_id: int, league_id: int | None, user_id: int) -> list[StarterData]:
        """Titulares del usuario: del equipo del partido (amistoso) o de la liga."""
    
    @abstractmethod
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son jugadores del usuario."""
        pass

    @abstractmethod
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son behaviors del usuario."""
        pass
