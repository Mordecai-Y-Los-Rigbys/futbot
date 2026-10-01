from sqlalchemy import func, select, literal
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
        
        # --- ESQUELETO DE DELETABLE ---
        # TODO: Reemplazar literal(True) por subconsultas EXISTS cuando
        # existan los modelos de Ligas y Partidos, chequear si esta en un partido en juego, 
        # o si esta en una liga no finalizada.
        is_deletable = literal(True).label("deletable")
        
        rows = self.db.execute(
            select(Player, is_deletable)
            .where(*filters)
            .order_by(Player.id.asc())
            .offset(offset)
            .limit(limit)
        ).all()
        
        result = []
        for player_obj, deletable_flag in rows:
            data = PlayerData.model_validate(player_obj)
            data.deletable = deletable_flag
            result.append(data)
    
        return result, total