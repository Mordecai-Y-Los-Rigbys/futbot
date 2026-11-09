from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.config import allowed_origins
from app.database import SessionLocal
from app.repositories.notification_abstract import NotificationsState
from app.repositories.notification_sqlalchemy import SqlAlchemyNotificationRepository
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.services.notifications_channel import NotificationsHandshakeService, NotificationsManager
from app.services.notifications_notifier import NotificationsNotifier
from app.services.session_service import SessionService


def _load_notifications_state(user_id: int) -> NotificationsState:
    with SessionLocal() as db:
        return SqlAlchemyNotificationRepository(db).get_state(user_id)


_notifications_manager = NotificationsManager(_load_notifications_state)


def get_notifications_manager() -> NotificationsManager:
    return _notifications_manager


def get_notifications_notifier() -> NotificationsNotifier:
    return _notifications_manager


@contextmanager
def _notifications_handshake_scope() -> Iterator[NotificationsHandshakeService]:
    with SessionLocal() as db:
        yield NotificationsHandshakeService(
            allowed_origins(), SessionService(SqlAlchemySessionRepository(db))
        )


def get_notifications_handshake_scope() -> (
    Callable[[], ContextManager[NotificationsHandshakeService]]
):
    return _notifications_handshake_scope
