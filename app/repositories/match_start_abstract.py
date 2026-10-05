from abc import ABC, abstractmethod


class AbstractMatchStartRepository(ABC):
    """Operaciones del arranque automático de un amistoso con rival."""

    @abstractmethod
    def start_if_ready(self, match_id: int) -> bool:
        """Pasa el partido a `started` solo si sigue siendo un amistoso
        `scheduled` con rival, en una única actualización condicional.
        Devuelve True si lo arrancó."""

    @abstractmethod
    def list_pending_start(self) -> list[int]:
        """Ids de los amistosos con rival que siguen `scheduled` (para
        reprogramar la cuenta regresiva al arrancar la app)."""