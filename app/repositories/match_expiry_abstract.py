from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class WaitingFriendlyData(BaseModel):
    match_id: int
    created_at: datetime


class AbstractMatchExpiryRepository(ABC):
    """Operaciones de la caducidad de amistosos sin rival.

    "Amistoso en espera" = partido sin liga, sin usuario 2 y en `scheduled`.
    """

    @abstractmethod
    def cancel_if_waiting_friendly(self, match_id: int) -> bool:
        """Pasa el partido a `cancelled` solo si sigue siendo un amistoso en
        espera, en una única actualización condicional. Devuelve True si lo
        canceló, False si ya no correspondía (se unió un rival, ya estaba
        cancelado, no existe, etc.)."""

    @abstractmethod
    def list_waiting_friendlies(self) -> list[WaitingFriendlyData]:
        """Amistosos en espera con su fecha de creación (para reprogramar
        los timers al arrancar la app)."""