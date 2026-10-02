from sqlalchemy.orm import Session

from app.models.match import Match, MatchStatus
from app.repositories.match_abstract import AbstractMatchRepository, MatchStateData


class SqlAlchemyMatchRepository(AbstractMatchRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_state(self, match_id: int) -> MatchStateData | None:
        record = self.db.get(Match, match_id)
        if record is None:
            return None
        return MatchStateData(
            id=record.id,
            finished=record.status == MatchStatus.finished,
        )