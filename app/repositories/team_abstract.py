from abc import ABC, abstractmethod
from pydantic import BaseModel


class StarterData(BaseModel):
    player_id: int
    role: str            # "defense" | "midfield" | "forward"
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