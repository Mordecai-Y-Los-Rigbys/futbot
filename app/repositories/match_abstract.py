from abc import ABC, abstractmethod
from pydantic import BaseModel
from app.domain.match import MatchStatus


class MatchStateData(BaseModel):
    id: int
    status: MatchStatus

class MatchSetupData(BaseModel):
    id: int
    league_id: int | None
    user_1_id: int
    user_2_id: int | None
    club_1_name: str
    club_2_name: str | None


class AbstractMatchRepository(ABC):
    @abstractmethod
    def get_state(self, match_id: int) -> MatchStateData | None:
        """Devuelve el estado mínimo del partido, o None si no existe."""
        pass
    
    @abstractmethod
    def get_setup_data(self, match_id: int) -> MatchSetupData | None:
        """Datos del partido y nombres de los clubes, o None si no existe."""
    
    @abstractmethod
    def mark_started(self, match_id: int) -> None:
        """Pasa el partido de scheduled a started."""

    @abstractmethod
    def finish(self, match_id: int, score_1: int, score_2: int) -> None:
        """Guarda el resultado y pasa el partido a finished."""