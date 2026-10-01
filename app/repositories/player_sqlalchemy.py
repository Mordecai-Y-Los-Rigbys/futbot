from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.player import Player
from app.repositories.player_abstract import (
    AbstractPlayerRepository, 
    PlayerData
)


class SqlAlchemyPlayerRepository(AbstractPlayerRepository):
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[PlayerData], int]:
        filters = [Player.user_id == user_id]
        
        if name:
            escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(Player.name.ilike(f"%{escaped}%", escape="\\"))

        total = self.db.scalar(
            select(func.count()).select_from(Player).where(*filters)
        ) or 0
        
        rows = self.db.scalars(
            select(Player)
            .where(*filters)
            .order_by(Player.id.asc())
            .offset(offset)
            .limit(limit)
        ).all()
    
        return [PlayerData.model_validate(p) for p in rows], total