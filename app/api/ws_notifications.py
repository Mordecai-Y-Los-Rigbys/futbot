from typing import Callable, ContextManager

from fastapi import APIRouter, Depends, WebSocket
from starlette.concurrency import run_in_threadpool

from app.api.ws_channel import reject, serve
from app.api.ws_notification_deps import (
    get_notifications_handshake_scope,
    get_notifications_manager,
)
from app.errors import ApiError
from app.services.notifications_channel import (
    NotificationsGrant,
    NotificationsHandshakeService,
    NotificationsManager,
)

router = APIRouter(tags=["notifications"])

HandshakeScope = Callable[[], ContextManager[NotificationsHandshakeService]]


@router.websocket("/ws/notifications")
async def notifications_stream(
    websocket: WebSocket,
    handshake_scope: HandshakeScope = Depends(get_notifications_handshake_scope),
    manager: NotificationsManager = Depends(get_notifications_manager),
) -> None:
    origin = websocket.headers.get("origin")
    session_id = websocket.cookies.get("session_id")

    def authorize() -> NotificationsGrant:
        with handshake_scope() as service:
            return service.authorize(origin, session_id)

    try:
        grant = await run_in_threadpool(authorize)
        # Las conexiones se registran por usuario: el user_id es la clave.
        manager.reserve(grant.user_id, grant.user_id)
    except ApiError as error:
        await reject(websocket, error)
        return

    await serve(
        websocket,
        manager,
        grant.user_id,
        grant.user_id,
        grant.session_id,
        grant.session_expires_at,
    )
