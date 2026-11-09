from abc import ABC, abstractmethod

from app.repositories.player_abstract import PlayerData


class AbstractBehaviorTestLineupRepository(ABC):
    """Lo que necesita el WebSocket de la prueba para armar los dos clubes."""

    @abstractmethod
    def behavior_codes(self, user_id: int, ids: set[int]) -> dict[int, str]:
        """El código de cada behavior del usuario entre `ids`, por id.
        Los que no existen no aparecen."""

    @abstractmethod
    def players(self, user_id: int, ids: list[int]) -> dict[int, PlayerData]:
        """Los jugadores del usuario entre `ids`, por id."""
