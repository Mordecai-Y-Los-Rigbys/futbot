from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.domain.behavior import BehaviorType


class BehaviorData(BaseModel):
    id: int
    user_id: int
    name: str
    code: str
    type: BehaviorType = BehaviorType.player_behavior

    model_config = {"from_attributes": True}


class CreateBehaviorData(BaseModel):
    name: str
    code: str
    type: BehaviorType = BehaviorType.player_behavior


class UpdateBehaviorData(BaseModel):
    name: str
    code: str


class DuplicateBehaviorNameError(Exception):
    """El usuario ya tiene un behavior con ese nombre."""


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
    def create_many(self, user_id: int, behaviors: list[CreateBehaviorData]) -> list[BehaviorData]:
        """Crea los behaviors para el usuario. No confirma la transacción."""

    @abstractmethod
    def name_taken(self, user_id: int, name: str, except_id: int | None = None) -> bool:
        """True si el usuario ya tiene un behavior con ese nombre, de cualquier tipo.

        Si se pasa `except_id`, ese behavior no se tiene en cuenta: al editarlo,
        su propio nombre no está repetido.
        """

    @abstractmethod
    def create(self, user_id: int, data: CreateBehaviorData) -> BehaviorData:
        """Crea el behavior y confirma la transacción.

        Raises:
            DuplicateBehaviorNameError: otro request creó el mismo nombre al mismo tiempo.
        """

    @abstractmethod
    def update(self, behavior_id: int, data: UpdateBehaviorData) -> BehaviorData | None:
        """Cambia nombre y código, y confirma la transacción.

        Devuelve None si el behavior ya no existe (se eliminó mientras tanto).

        Raises:
            DuplicateBehaviorNameError: otro request usó el mismo nombre al mismo tiempo.
        """

    @abstractmethod
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son behaviors del usuario."""

    @abstractmethod
    def behavior_types(self, user_id: int, ids: list[int]) -> dict[int, BehaviorType]:
        """Tipo de cada behavior de `ids` que pertenece al usuario.

        Los ids ajenos o inexistentes no aparecen en el resultado.
        """
