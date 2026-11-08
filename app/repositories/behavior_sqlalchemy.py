from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.behavior import Behavior, BehaviorType
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    CreateBehaviorData,
    DuplicateBehaviorNameError,
    UpdateBehaviorData,
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

    def name_taken(self, user_id: int, name: str, except_id: int | None = None) -> bool:
        query = select(Behavior.id).where(Behavior.user_id == user_id, Behavior.name == name)
        if except_id is not None:
            query = query.where(Behavior.id != except_id)
        return self.db.scalar(query) is not None

    def create(self, user_id: int, data: CreateBehaviorData) -> BehaviorData:
        record = Behavior(user_id=user_id, name=data.name, code=data.code, type=data.type)
        self.db.add(record)
        try:
            self.db.commit()
        except IntegrityError as error:
            # La restricción única (user_id, name) frena a dos requests simultáneos
            # que pasaron el chequeo de name_taken con el mismo nombre.
            self.db.rollback()
            raise DuplicateBehaviorNameError() from error
        return BehaviorData.model_validate(record)

    def update(self, behavior_id: int, data: UpdateBehaviorData) -> BehaviorData | None:
        # Un solo UPDATE: si el behavior se eliminó después de leerlo, no toca ninguna fila.
        query = (
            update(Behavior)
            .where(Behavior.id == behavior_id)
            .values(name=data.name, code=data.code)
            .returning(Behavior)
        )
        try:
            record = self.db.execute(query).scalar_one_or_none()
            result = BehaviorData.model_validate(record) if record is not None else None
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise DuplicateBehaviorNameError() from error
        return result

    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        return set(
            self.db.scalars(
                select(Behavior.id).where(Behavior.user_id == user_id, Behavior.id.in_(ids))
            )
        )

    def behavior_types(self, user_id: int, ids: list[int]) -> dict[int, BehaviorType]:
        if not ids:
            return {}
        rows = self.db.execute(
            select(Behavior.id, Behavior.type).where(
                Behavior.user_id == user_id, Behavior.id.in_(ids)
            )
        ).all()
        return {behavior_id: BehaviorType(kind) for behavior_id, kind in rows}
