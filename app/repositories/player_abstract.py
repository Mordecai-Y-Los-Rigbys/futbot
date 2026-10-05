from abc import ABC, abstractmethod

from pydantic import BaseModel


class CreatePlayerData(BaseModel):
    name: str
    power: int
    agility: int
    control: int
    strength: int
    speed: int


class PlayerData(BaseModel):
    id: int
    user_id: int
    name: str
    power: int
    agility: int
    control: int
    strength: int
    speed: int

    deletable: bool = False

    model_config = {"from_attributes": True}


class AbstractPlayerRepository(ABC):
    @abstractmethod
    def create(self, user_id: int, data: CreatePlayerData) -> PlayerData:
        """Crea un nuevo jugador y lo asocia al usuario."""

    @abstractmethod
    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[PlayerData], int]:
        """Devuelve la plantilla de jugadores pertenecientes al usuario."""

    @abstractmethod
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son jugadores del usuario."""
