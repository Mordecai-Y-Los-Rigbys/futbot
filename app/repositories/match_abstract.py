from abc import ABC, abstractmethod
from pydantic import BaseModel


class MatchStateData(BaseModel):
    id: int
    status: str


class AbstractMatchRepository(ABC):
    @abstractmethod
    def get_state(self, match_id: int) -> MatchStateData | None:
        """Devuelve el estado mínimo del partido, o None si no existe."""
        pass
    
    @abstractmethod
    def get_setup_data(self, match_id: int) -> MatchSetupData | None:
        """Datos del partido y nombres de los clubes, o None si no existe."""