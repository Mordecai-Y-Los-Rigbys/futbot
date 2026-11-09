from typing import Any

from app.errors import ApiError, ValidationApiError
from app.repositories.notification_abstract import NotificationRepository
from app.services.field_validation import field_error, id_reason
from app.services.league_validation import INVALID_JSON
from app.services.notifications_notifier import NotificationsNotifier

FIELD = "notificationId"


def parse_mark_seen(body: Any) -> int:
    """Valida el body de POST /notifications/seen y devuelve el id."""
    if body is INVALID_JSON or not isinstance(body, dict):
        raise ValidationApiError([field_error(FIELD, "required")])
    reason = id_reason(body, FIELD)
    if reason is not None:
        raise ValidationApiError([field_error(FIELD, reason)])
    return body[FIELD]


class NotificationService:
    def __init__(self, repository: NotificationRepository, notifier: NotificationsNotifier) -> None:
        self.repository = repository
        self.notifier = notifier

    def mark_seen(self, user_id: int, body: Any) -> None:
        """Marca como vistas la notificación indicada y las anteriores del usuario.

        Raises:
            ValidationApiError 400 invalidFields: notificationId falta, no es entero
                o está fuera de rango.
            ApiError 409 notificationNotOwned: no existe o es de otro usuario.
        """
        notification_id = parse_mark_seen(body)
        if not self.repository.mark_seen_up_to(user_id, notification_id):
            raise ApiError(
                409, "notificationNotOwned", "La notificación no existe o no es tuya."
            )
        # Después del commit: actualiza todas las conexiones del usuario.
        self.notifier.notifications_changed([user_id])
