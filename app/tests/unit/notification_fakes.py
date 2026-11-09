from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.repositories.friendly_abstract import FriendlyClubData
from app.repositories.match_abstract import PenaltyShootoutData
from app.repositories.notification_abstract import (
    NOTIFICATIONS_LIMIT,
    FinishedMatchData,
    NotificationData,
    NotificationsState,
)

BASE_TIME = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)


def club(user_id: int, avatar: int = 1) -> FriendlyClubData:
    return FriendlyClubData(
        id=user_id, username=f"user{user_id}", club_name=f"club{user_id}", avatar=avatar
    )


def match_notification(
    notification_id: int,
    league_match_id: int = 50,
    minute: int = 0,
    seen: bool = False,
    penalties: PenaltyShootoutData | None = None,
) -> NotificationData:
    return NotificationData(
        id=notification_id,
        league_id=1,
        league_match_id=league_match_id,
        seen=seen,
        created_at=BASE_TIME + timedelta(minutes=minute),
        league_name="Liga",
        match=FinishedMatchData(
            club1=club(7, avatar=2),
            club2=club(8, avatar=4),
            score_1=2,
            score_2=1,
            penalties=penalties,
        ),
    )


def league_notification(notification_id: int, minute: int = 0, seen: bool = False):
    return NotificationData(
        id=notification_id,
        league_id=1,
        league_match_id=None,
        seen=seen,
        created_at=BASE_TIME + timedelta(minutes=minute),
        league_name="Liga",
        match=None,
    )


class FakeNotifications:
    """Notificaciones por usuario y participantes por liga, sin base."""

    def __init__(self):
        self.by_user: dict[int, list[NotificationData]] = {}
        self.participants: dict[int, list[int]] = {}
        self.state_reads: list[int] = []

    def add(self, user_id: int, notification: NotificationData):
        self.by_user.setdefault(user_id, []).append(notification)

    def mark_all_seen(self, user_id: int):
        self.by_user[user_id] = [replace(n, seen=True) for n in self.by_user.get(user_id, [])]

    def get_state(self, user_id: int) -> NotificationsState:
        self.state_reads.append(user_id)
        mine = self.by_user.get(user_id, [])
        ordered = sorted(mine, key=lambda n: (n.created_at, n.id), reverse=True)
        return NotificationsState(
            has_unseen=any(not n.seen for n in mine),
            notifications=ordered[:NOTIFICATIONS_LIMIT],
        )

    def recipients(self, league_id: int) -> list[int]:
        return list(self.participants.get(league_id, []))

    def mark_seen_up_to(self, user_id: int, notification_id: int) -> bool:
        mine = self.by_user.get(user_id, [])
        if all(n.id != notification_id for n in mine):
            return False
        self.by_user[user_id] = [
            replace(n, seen=True) if n.id <= notification_id else n for n in mine
        ]
        return True
