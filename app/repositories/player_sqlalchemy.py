from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.player import Player
from app.repositories.player_abstract import AbstractPlayerRepository, PlayerData


class SqlAlchemyPlayerRepository(AbstractPlayerRepository):
    def __init__(self, db: Session):
        self.db = db

    def list_by_user_id(self, user_id: int) -> list[PlayerData]:
        stmt = select(Player).where(Player.user_id == user_id).order_by(Player.id.asc())
        players = self.db.scalars(stmt).all()
        return [PlayerData.model_validate(p) for p in players]