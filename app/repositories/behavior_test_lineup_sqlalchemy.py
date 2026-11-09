from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.player import Player
from app.repositories.behavior_test_lineup_abstract import AbstractBehaviorTestLineupRepository
from app.repositories.player_abstract import PlayerData


class SqlAlchemyBehaviorTestLineupRepository(AbstractBehaviorTestLineupRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def behavior_codes(self, user_id: int, ids: set[int]) -> dict[int, str]:
        rows = self.db.execute(
            select(Behavior.id, Behavior.code).where(
                Behavior.user_id == user_id, Behavior.id.in_(ids)
            )
        ).all()
        return {behavior_id: code for behavior_id, code in rows}

    def players(self, user_id: int, ids: list[int]) -> dict[int, PlayerData]:
        rows = self.db.scalars(
            select(Player).where(Player.user_id == user_id, Player.id.in_(ids))
        ).all()
        return {player.id: PlayerData.model_validate(player) for player in rows}
