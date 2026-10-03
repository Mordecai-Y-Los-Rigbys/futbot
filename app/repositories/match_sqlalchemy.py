from sqlalchemy.orm import Session

from app.models.match import Match
from app.repositories.match_abstract import AbstractMatchRepository, MatchStateData


class SqlAlchemyMatchRepository(AbstractMatchRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_state(self, match_id: int) -> MatchStateData | None:
        record = self.db.get(Match, match_id)
        if record is None:
            return None

        return MatchStateData(id=record.id, status=record.status.value)
    
    from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.match import Match
from app.models.user import User
from app.repositories.match_abstract import (
    AbstractMatchRepository,
    MatchSetupData,
    MatchStateData,
)


class SqlAlchemyMatchRepository(AbstractMatchRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_state(self, match_id: int) -> MatchStateData | None:
        record = self.db.get(Match, match_id)
        if record is None:
            return None
        return MatchStateData(id=record.id, status=record.status.value)

    def get_setup_data(self, match_id: int) -> MatchSetupData | None:
        user_1 = aliased(User)
        user_2 = aliased(User)

        row = self.db.execute(
            select(
                Match.id,
                Match.league_id,
                Match.user_1_id,
                Match.user_2_id,
                user_1.club_name.label("club_1_name"),
                user_2.club_name.label("club_2_name"),
            )
            .join(user_1, user_1.id == Match.user_1_id)
            .outerjoin(user_2, user_2.id == Match.user_2_id)  # outer: puede no haber rival
            .where(Match.id == match_id)
        ).one_or_none()

        if row is None:
            return None

        return MatchSetupData(
            id=row.id,
            league_id=row.league_id,
            user_1_id=row.user_1_id,
            user_2_id=row.user_2_id,
            club_1_name=row.club_1_name,
            club_2_name=row.club_2_name,
        )