from typing import Any

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user_id, get_json_body, get_notification_service
from app.schemas.errors import Error, MarkNotificationsSeenConflict, ValidationBadRequest
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "/seen",
    status_code=204,
    response_class=Response,
    operation_id="markNotificationsSeen",
    summary="Marcar como vistas una notificación y las anteriores",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        409: {"model": MarkNotificationsSeenConflict},
    },
)
def mark_notifications_seen(
    user_id: int = Depends(get_current_user_id),
    body: Any = Depends(get_json_body),
    service: NotificationService = Depends(get_notification_service),
) -> Response:
    service.mark_seen(user_id, body)
    return Response(status_code=204)
