from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
)

PAGE_SIZE = 50


class BehaviorService:
    def __init__(self, repository: AbstractBehaviorRepository):
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