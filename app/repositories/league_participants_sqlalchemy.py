from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.league import LeagueStatus
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.user import User
from app.repositories.league_participants_abstract import (
    LeagueParticipantsState,
    ParticipantData,
)


class SqlAlchemyLeagueParticipantsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_status(self, league_id: int) -> LeagueStatus | None:
        status = self.db.scalar(select(League.status).where(League.id == league_id))
        return None if status is None else LeagueStatus(status)

    def get_state(self, league_id: int) -> LeagueParticipantsState | None:
        league = self.db.execute(
            select(League.status, League.creator_id).where(League.id == league_id)
        ).one_or_none()
        if league is None:
            return None

        rows = self.db.execute(
            select(User.id, User.username, User.club_name, User.avatar)
            .join(LeagueParticipant, LeagueParticipant.user_id == User.id)
            .where(LeagueParticipant.league_id == league_id)
            .order_by((User.id == league.creator_id).desc(), User.id.asc())
        ).all()

        return LeagueParticipantsState(
            status=LeagueStatus(league.status),
            participants=[
                ParticipantData(
                    id=r.id, username=r.username, club_name=r.club_name, avatar=r.avatar
                )
                for r in rows
            ],
        )
