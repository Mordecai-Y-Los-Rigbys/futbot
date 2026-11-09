from collections.abc import Iterable
from typing import Protocol


class NotificationsNotifier(Protocol):
    def notifications_changed(self, user_ids: Iterable[int]) -> None:
        """Reenvía el estado completo por /ws/notifications a esos usuarios."""
