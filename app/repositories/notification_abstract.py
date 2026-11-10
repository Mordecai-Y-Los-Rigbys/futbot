from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.repositories.friendly_abstract import FriendlyClubData
from app.repositories.match_abstract import PenaltyShootoutData

NOTIFICATIONS_LIMIT = 10


@dataclass(frozen=True)
class FinishedMatchData:
    """El partido de una notificación de fin de partido."""

    club1: FriendlyClubData
    club2: FriendlyClubData
    score_1: int
    score_2: int
    penalties: PenaltyShootoutData | None


@dataclass(frozen=True)
class NotificationData:
    id: int
    league_id: int
    league_match_id: int | None  # None: fin de liga
    seen: bool
    created_at: datetime
    league_name: str
    match: FinishedMatchData | None  # None: fin de liga


@dataclass(frozen=True)
class NotificationsState:
    """Lo que se envía por /ws/notifications."""

    has_unseen: bool  # contando todas, no solo las de `notifications`
    notifications: list[NotificationData]  # por created_at desc y después id desc


class NotificationRepository(Protocol):
    def get_state(self, user_id: int) -> NotificationsState:
        """Las NOTIFICATIONS_LIMIT más recientes del usuario y si tiene alguna sin ver."""
        ...

    def recipients(self, league_id: int) -> list[int]:
        """Usuarios que reciben las notificaciones de la liga: sus participantes."""
        ...
