from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class PendingLeagueMatch(BaseModel):
    match_id: int
    scheduled_at: datetime


class AbstractLeagueMatchStartRepository(ABC):
    """Operaciones del arranque automático de los partidos de liga."""
    
    @abstractmethod
    def is_ready_to_start(self, match_id: int) -> bool:
        """True si es un partido de liga que sigue `scheduled`. No cambia su estado."""
        
    @abstractmethod
    def list_pending_start(self, league_id: int | None = None) -> list[PendingLeagueMatch]:
        """Partidos de liga que siguen `scheduled`, con su horario.

        Con `league_id`, solo los de esa liga (al iniciarla). Sin él, los de
        todas las ligas (para reprogramarlos al arrancar la app).
        """