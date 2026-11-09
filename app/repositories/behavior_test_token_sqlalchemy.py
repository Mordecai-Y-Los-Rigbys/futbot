from datetime import timezone

from sqlalchemy.orm import Session

from app.models.behavior_test_token import BehaviorTestToken
from app.repositories.behavior_test_token_abstract import (
    AbstractBehaviorTestTokenRepository,
    BehaviorTestTokenData,
    CreateBehaviorTestTokenData,
)


class SqlAlchemyBehaviorTestTokenRepository(AbstractBehaviorTestTokenRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: CreateBehaviorTestTokenData) -> None:
        self.db.add(
            BehaviorTestToken(
                **data.model_dump(exclude={"members"}),
                members=[m.model_dump(mode="json") for m in data.members],
            )
        )
        self.db.commit()

    def get_by_token(self, token: str) -> BehaviorTestTokenData | None:
        record = self.db.get(BehaviorTestToken, token)
        if record is None:
            return None
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return BehaviorTestTokenData(
            token=record.token,
            user_id=record.user_id,
            behavior_id=record.behavior_id,
            expires_at=expires_at,
            members=record.members,
        )
