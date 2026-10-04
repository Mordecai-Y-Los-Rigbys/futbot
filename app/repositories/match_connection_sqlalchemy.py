from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.match_ws_token import MatchWsToken
from app.repositories.match_connection_abstract import (
    AbstractMatchConnectionRepository,
    CreateMatchWsTokenData,
    MatchAccessData,
)


class SqlAlchemyMatchConnectionRepository(AbstractMatchConnectionRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_access(self, match_id: int) -> MatchAccessData | None:
        row = self.db.execute(
            select(
                Match.id,
                Match.status,
                Match.league_id,
                League.creator_id,
                League.private,
                League.password,
            )
            .outerjoin(League, League.id == Match.league_id)
            .where(Match.id == match_id)
        ).first()
        if row is None:
            return None
        return MatchAccessData(
            id=row.id,
            status=row.status.value,
            league_id=row.league_id,
            league_creator_id=row.creator_id,
            league_private=bool(row.private),
            league_password=row.password,
        )

    def is_league_participant(self, league_id: int, user_id: int) -> bool:
        return (
            self.db.scalar(
                select(LeagueParticipant.user_id).where(
                    LeagueParticipant.league_id == league_id,
                    LeagueParticipant.user_id == user_id,
                )
            )
            is not None
        )

    def create_token(self, data: CreateMatchWsTokenData) -> None:
        try:
            self.db.add(MatchWsToken(**data.model_dump()))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise