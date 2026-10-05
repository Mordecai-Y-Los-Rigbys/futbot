from sqlalchemy import func, select, literal
from sqlalchemy.orm import Session

from app.models.player import Player
from app.repositories.player_abstract import (
    AbstractPlayerRepository, 
    PlayerData
)
from app.services.player_validation import CreatePlayerInput

class SqlAlchemyPlayerRepository(AbstractPlayerRepository):
    def __init__(self, db: Session):
        self.db = db
        
    def create(self, user_id: int, data: CreatePlayerInput) -> PlayerData:
        player = Player(
            user_id=user_id,
            name=data.name,       
            power=data.power,
            agility=data.agility,
            control=data.control,
            strength=data.strength,
            speed=data.speed
        )
        self.db.add(player)
        self.db.flush()
        self.db.commit()
        self.db.refresh(player)
        
        result = PlayerData.model_validate(player)
        result.deletable = True 
        return result

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
        # TODO: Reemplazar literal(True) por subconsultas EXISTS en el tercer
        # sprint, chequear si esta en un partido en juego, 
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
    
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]:
        return set(self.db.scalars(
            select(Player.id).where(Player.user_id == user_id, Player.id.in_(ids))
        ))