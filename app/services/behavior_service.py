from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior

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