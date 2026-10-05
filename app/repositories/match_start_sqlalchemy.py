from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.domain.match import MatchStatus
from app.models.match import Match
from app.repositories.match_start_abstract import AbstractMatchStartRepository


class SqlAlchemyMatchStartRepository(AbstractMatchStartRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def ready_condition():
        """Amistoso (sin liga) con rival que todavía no arrancó."""
        return and_(
            Match.league_id.is_(None),
            Match.user_2_id.is_not(None),
            Match.status == MatchStatus.scheduled,
        )

    def is_ready_to_start(self, match_id: int) -> bool:
        found = self.db.scalar(
            select(Match.id).where(Match.id == match_id, self.ready_condition())
        )
        return found is not None

    def list_pending_start(self) -> list[int]:
        return list(
            self.db.scalars(
                select(Match.id).where(self.ready_condition()).order_by(Match.id.asc())
            )
        )