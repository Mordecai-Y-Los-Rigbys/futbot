from datetime import timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.match import Match, MatchStatus
from app.repositories.match_expiry_abstract import (
    AbstractMatchExpiryRepository,
    WaitingFriendlyData,
)


def _is_waiting_friendly():
    # Misma condición que tiene que usar el endpoint de unirse al amistoso
    # (UPDATE ... SET user_2_id = :rival WHERE user_2_id IS NULL ...): la base
    # decide quién gana la carrera entre el rival y el vencimiento.
    return (
        Match.league_id.is_(None),
        Match.user_2_id.is_(None),
        Match.status == MatchStatus.scheduled,
    )


class SqlAlchemyMatchExpiryRepository(AbstractMatchExpiryRepository):
    def __init__(self, db: Session):
        self.db = db

    def cancel_if_waiting_friendly(self, match_id: int) -> bool:
        try:
            result = self.db.execute(
                update(Match)
                .where(Match.id == match_id, *_is_waiting_friendly())
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
            .where(*_is_waiting_friendly())
            .order_by(Match.id.asc())
        ).all()

        result = []
        for match_id, created_at in rows:
            # Igual que en los otros repos: DateTime naive -> UTC.
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            result.append(WaitingFriendlyData(match_id=match_id, created_at=created_at))
        return result