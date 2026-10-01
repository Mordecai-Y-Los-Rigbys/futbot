from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class PlayerData(BaseModel):
    id: int
    user_id: int
    name: str
    power: int
    agility: int
    control: int
    strength: int
    speed: int

    model_config = ConfigDict(from_attributes=True)


class AbstractPlayerRepository(ABC):
    @abstractmethod
    def list_by_user_id(self, user_id: int) -> list[PlayerData]:
        """Devuelve la plantilla de jugadores pertenecientes al usuario."""
        pass