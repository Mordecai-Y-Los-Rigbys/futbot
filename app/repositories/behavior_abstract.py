from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.domain.behavior import BehaviorType, BehaviorUsage


class BehaviorData(BaseModel):
    id: int
    user_id: int
    name: str
    code: str
    type: BehaviorType = BehaviorType.player_behavior
    deleted: bool = False

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


class BehaviorNotFoundError(Exception):
    """El behavior no existe o ya está eliminado."""


class AbstractBehaviorRepository(ABC):
    @abstractmethod
    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[BehaviorData], int]:
        """
        Devuelve (items de la ventana offset/limit, total que matchea el filtro).
        Siempre filtra por user_id; name es un contains case-insensitive opcional.
        No incluye los behaviors eliminados.
        """

    @abstractmethod
    def get_by_id(self, behavior_id: int) -> BehaviorData | None:
        """Devuelve el behavior con ese id (de cualquier usuario) o None si no existe.

        También devuelve los eliminados, con `deleted` en True.
        """

    @abstractmethod
    def create_many(self, user_id: int, behaviors: list[CreateBehaviorData]) -> list[BehaviorData]:
        """Crea los behaviors para el usuario. No confirma la transacción."""

    @abstractmethod
    def name_taken(self, user_id: int, name: str, except_id: int | None = None) -> bool:
        """True si el usuario ya tiene un behavior no eliminado con ese nombre, de cualquier tipo.

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

        Devuelve None si el behavior se eliminó mientras tanto.

        Raises:
            DuplicateBehaviorNameError: otro request usó el mismo nombre al mismo tiempo.
        """

    @abstractmethod
    def usage(self, behavior_id: int) -> BehaviorUsage | None:
        """Por qué el behavior está en uso, o None si se puede eliminar.

        En uso: asignado a un jugador o como DT en un equipo de una liga en
        preparación o en curso (league_team), o a un jugador de un amistoso que
        no terminó (match). Si se dan los dos, devuelve league_team.
        """

    @abstractmethod
    def delete_if_unused(self, behavior_id: int) -> BehaviorUsage | None:
        """Marca el behavior como eliminado si no está en uso, y confirma la transacción.

        El chequeo y el borrado son atómicos: nadie puede asignarlo a un equipo
        en el medio. Devuelve por qué está en uso (y no lo elimina), o None.

        Raises:
            BehaviorNotFoundError: ya estaba eliminado (otro DELETE lo eliminó
                mientras tanto). No calcula el uso ni toca la fila.
        """

    @abstractmethod
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son behaviors no eliminados del usuario.

        Los bloquea hasta el fin de la transacción, para que no se eliminen
        mientras se arma el equipo.
        """

    @abstractmethod
    def behavior_types(self, user_id: int, ids: list[int]) -> dict[int, BehaviorType]:
        """Tipo de cada behavior de `ids` que pertenece al usuario y no está eliminado.

        Los ids ajenos, inexistentes o eliminados no aparecen en el resultado.
        Los bloquea como `owned_behavior_ids`.
        """
