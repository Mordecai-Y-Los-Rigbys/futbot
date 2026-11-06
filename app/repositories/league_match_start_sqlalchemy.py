from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.match import MatchStatus
from app.models.match import Match
from app.repositories.league_match_start_abstract import (
    AbstractLeagueMatchStartRepository,
    PendingLeagueMatch,
)


class SqlAlchemyLeagueMatchStartRepository(AbstractLeagueMatchStartRepository):
    def __init__(self, db: Session) -> None:
        self.db = db
        
    def is_ready_to_start(self, match_id: int) -> bool:
        found = self.db.scalar(
            select(Match.id).where(
                Match.id == match_id,
                Match.league_id.is_not(None),
                Match.status == MatchStatus.scheduled
            )
        )
        return found is not None
    
    def list_pending_start(self, league_id: int | None = None) -> list[PendingLeagueMatch]:
        query = select(Match.id, Match.scheduled_at).where(
            Match.league_id.is_not(None), 
            Match.status == MatchStatus.scheduled
        )
        if league_id is not None:
            query = query.where(Match.league_id == league_id)
        
        rows = self.db.execute(query.order_by(Match.scheduled_at, Match.id))
        return [PendingLeagueMatch(match_id=r.id, scheduled_at=r.scheduled_at) for r in rows]
