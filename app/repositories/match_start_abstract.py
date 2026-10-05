from abc import ABC, abstractmethod


class AbstractMatchStartRepository(ABC):
    """Operaciones del arranque automático de un amistoso con rival."""

    @abstractmethod
    def is_ready_to_start(self, match_id: int) -> bool:
        """True si el partido sigue siendo un amistoso `scheduled` con rival,
        es decir, si corresponde arrancar la simulación. No cambia su estado."""

    @abstractmethod
    def list_pending_start(self) -> list[int]:
        """Ids de los amistosos con rival que siguen `scheduled` (para
        reprogramar la cuenta regresiva al arrancar la app)."""