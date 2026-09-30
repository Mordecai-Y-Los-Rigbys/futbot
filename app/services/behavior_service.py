from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.errors import ApiError

PAGE_SIZE = 50


class BehaviorService:
    def __init__(self, db: Session):
        self.db = db

    def list_behaviors(
        self, user_id: int, name: str | None, page: int
    ) -> tuple[list[Behavior], int]:
        """
        Devuelve (items de la página, total que matchea el filtro).
        Siempre filtra por user_id; name es un contains case-insensitive opcional.
        """
        filters = [Behavior.user_id == user_id]
        if name:
            filters.append(Behavior.name.ilike(f"%{name}%"))

        total = self.db.scalar(
            select(func.count()).select_from(Behavior).where(*filters)
        )

        offset = (page - 1) * PAGE_SIZE
        items = (
            self.db.execute(
                select(Behavior)
                .where(*filters)
                .order_by(Behavior.id.asc())
                .offset(offset)
                .limit(PAGE_SIZE)
            )
            .scalars()
            .all()
        )

        return list(items), total or 0

    def get_owned_behavior(self, user_id: int, behavior_id: int) -> Behavior:
        behavior = self.db.get(Behavior, behavior_id)
        if behavior is None:
            raise ApiError(404, None, "Comportamiento no encontrado.")
        if behavior.user_id != user_id:
            raise ApiError(403, None, "El comportamiento no pertenece al usuario.")
        return behavior

