from datetime import timezone

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.models.match import Match, MatchStatus
from app.repositories.match_expiry_abstract import (
    AbstractMatchExpiryRepository,
    WaitingFriendlyData,
)


class SqlAlchemyMatchExpiryRepository(AbstractMatchExpiryRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def is_waiting_friendly():
        """Condición SQL de un amistoso esperando rival: sin liga, sin usuario 2
        y todavía sin arrancar."""
        return and_(
            Match.league_id.is_(None),
            Match.user_2_id.is_(None),
            Match.status == MatchStatus.scheduled,
        )

    def cancel_if_waiting_friendly(self, match_id: int) -> bool:
        try:
            result = self.db.execute(
                update(Match)
                .where(Match.id == match_id, self.is_waiting_friendly())
                .values(status=MatchStatus.cancelled)
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result.rowcount == 1

    def list_waiting_friendlies(self) -> list[WaitingFriendlyData]:
        rows = self.db.execute(
            select(Match.id, Match.created_at)
            .where(self.is_waiting_friendly())
            .order_by(Match.id.asc())
        ).all()

        result = []
        for match_id, created_at in rows:
            # Igual que en los otros repos: DateTime naive -> UTC.
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            result.append(WaitingFriendlyData(match_id=match_id, created_at=created_at))
        return result