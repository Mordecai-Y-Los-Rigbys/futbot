from abc import ABC, abstractmethod

from pydantic import BaseModel


class BehaviorData(BaseModel):
    id: int
    user_id: int
    name: str
    code: str

    model_config = {"from_attributes": True}

class CreateBehaviorData(BaseModel):
    name: str
    code: str

class AbstractBehaviorRepository(ABC):
    @abstractmethod
    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[BehaviorData], int]:
        """
        Devuelve (items de la ventana offset/limit, total que matchea el filtro).
        Siempre filtra por user_id; name es un contains case-insensitive opcional.
        """

    @abstractmethod
    def get_by_id(self, behavior_id: int) -> BehaviorData | None:
        """Devuelve el behavior con ese id (de cualquier usuario) o None si no existe."""
    
    @abstractmethod
    def create_many(
        self, user_id: int, behaviors: list[CreateBehaviorData]
    ) -> list[BehaviorData]:
        """Crea los behaviors para el usuario. No confirma la transacción."""