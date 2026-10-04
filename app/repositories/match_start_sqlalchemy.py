from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.models.match import Match, MatchStatus
from app.repositories.match_start_abstract import AbstractMatchStartRepository


class SqlAlchemyMatchStartRepository(AbstractMatchStartRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def is_ready_to_start():
        """Amistoso (sin liga) con rival que todavía no arrancó."""
        return and_(
            Match.league_id.is_(None),
            Match.user_2_id.is_not(None),
            Match.status == MatchStatus.scheduled,
        )

    def start_if_ready(self, match_id: int) -> bool:
        try:
            result = self.db.execute(
                update(Match)
                .where(Match.id == match_id, self.is_ready_to_start())
                .values(status=MatchStatus.started)
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result.rowcount == 1

    def list_pending_start(self) -> list[int]:
        return list(
            self.db.scalars(
                select(Match.id).where(self.is_ready_to_start()).order_by(Match.id.asc())
            )
        )