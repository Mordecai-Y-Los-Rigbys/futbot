from app.errors import ApiError
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    CreateBehaviorData,
)
from app.simulation.behaviors.default_behaviors import DEFAULT_BEHAVIORS

PAGE_SIZE = 50


class BehaviorService:
    """Casos de uso de los behaviors de un usuario: listar, ver y crear los iniciales."""

    def __init__(self, repository: AbstractBehaviorRepository) -> None:
        self.repository = repository

    def list_behaviors(
        self, user_id: int, name: str | None, page: int
    ) -> tuple[list[BehaviorData], int]:
        """
        Devuelve (items de la página, total que matchea el filtro).
        Siempre filtra por user_id; name es un contains case-insensitive opcional.
        """
        offset = (page - 1) * PAGE_SIZE
        return self.repository.list_by_user(
            user_id=user_id, name=name, offset=offset, limit=PAGE_SIZE
        )

    def get_owned_behavior(self, user_id: int, behavior_id: int) -> BehaviorData:
        """404 si no existe, 403 si es de otro usuario. Solo lectura."""
        behavior = self.repository.get_by_id(behavior_id)
        if behavior is None:
            raise ApiError(404, None, "Comportamiento no encontrado.")
        if behavior.user_id != user_id:
            raise ApiError(403, None, "El comportamiento no pertenece al usuario.")
        return behavior

    def create_default_behaviors(self, user_id: int) -> list[BehaviorData]:
        """Crea para el usuario una copia propia de los behaviors iniciales."""
        return self.repository.create_many(
            user_id, [CreateBehaviorData(**b) for b in DEFAULT_BEHAVIORS]
        )
