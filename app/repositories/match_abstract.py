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