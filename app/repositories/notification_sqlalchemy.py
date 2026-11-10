from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.notification import Notification
from app.models.user import User
from app.repositories.friendly_sqlalchemy import to_club_data
from app.repositories.match_sqlalchemy import to_penalty_data
from app.repositories.notification_abstract import (
    NOTIFICATIONS_LIMIT,
    FinishedMatchData,
    NotificationData,
    NotificationRepository,
    NotificationsState,
)


def _utc(value: datetime) -> datetime:
    # SQLite devuelve DateTime naive.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _to_notification(row) -> NotificationData:
    notification, league_name, match, user_1, user_2 = row
    finished = None
    if match is not None:
        finished = FinishedMatchData(
            club1=to_club_data(user_1),
            club2=to_club_data(user_2),
            score_1=match.score_1,
            score_2=match.score_2,
            penalties=to_penalty_data(match),
        )
    return NotificationData(
        id=notification.id,
        league_id=notification.league_id,
        league_match_id=notification.league_match_id,
        seen=notification.seen,
        created_at=_utc(notification.created_at),
        league_name=league_name,
        match=finished,
    )


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_state(self, user_id: int) -> NotificationsState:
        user_1 = aliased(User)
        user_2 = aliased(User)
        rows = self.db.execute(
            select(Notification, League.name, Match, user_1, user_2)
            .join(League, League.id == Notification.league_id)
            .outerjoin(Match, Match.id == Notification.league_match_id)
            .outerjoin(user_1, user_1.id == Match.user_1_id)
            .outerjoin(user_2, user_2.id == Match.user_2_id)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(NOTIFICATIONS_LIMIT)
        ).all()
        has_unseen = self.db.scalar(
            select(
                select(Notification.id)
                .where(Notification.user_id == user_id, Notification.seen.is_(False))
                .exists()
            )
        )
        return NotificationsState(
            has_unseen=bool(has_unseen), notifications=[_to_notification(r) for r in rows]
        )

    def recipients(self, league_id: int) -> list[int]:
        return list(
            self.db.scalars(
                select(LeagueParticipant.user_id).where(LeagueParticipant.league_id == league_id)
            )
        )
