from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    CreateBehaviorData,
)


class SqlAlchemyBehaviorRepository(AbstractBehaviorRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[BehaviorData], int]:
        filters = [Behavior.user_id == user_id]
        if name:
            escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(Behavior.name.ilike(f"%{escaped}%", escape="\\"))

        total = self.db.scalar(select(func.count()).select_from(Behavior).where(*filters))

        rows = (
            self.db.execute(
                select(Behavior)
                .where(*filters)
                .order_by(Behavior.id.asc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [BehaviorData.model_validate(r) for r in rows], total or 0

    def get_by_id(self, behavior_id: int) -> BehaviorData | None:
        record = self.db.get(Behavior, behavior_id)
        return BehaviorData.model_validate(record) if record is not None else None

    def create_many(self, user_id: int, behaviors: list[CreateBehaviorData]) -> list[BehaviorData]:
        records = [Behavior(user_id=user_id, name=b.name, code=b.code) for b in behaviors]
        self.db.add_all(records)
        self.db.flush()
        return [BehaviorData.model_validate(r) for r in records]

    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        return set(
            self.db.scalars(
                select(Behavior.id).where(Behavior.user_id == user_id, Behavior.id.in_(ids))
            )
        )
