from typing import Callable, ContextManager

from fastapi import APIRouter, Depends, Query, WebSocket
from starlette.concurrency import run_in_threadpool

from app.api.ws_deps import get_connection_manager, get_handshake_service_scope
from app.errors import ApiError
from app.services.match_connection_manager import MatchConnectionManager
from app.services.match_handshake_service import HandshakeGrant, MatchHandshakeService

router = APIRouter(tags=["matches"])


async def _reject(websocket: WebSocket, error: ApiError) -> None:
    """Rechaza la conexión: se acepta el upgrade y se cierra enseguida con
    código 4000 + status HTTP y `reason` = código del error."""
    await websocket.accept()
    await websocket.close(code=4000 + error.status_code, reason=error.code or "")


@router.websocket("/ws/matches/{match_id}")
async def match_stream(
    websocket: WebSocket,
    match_id: str,
    token: str | None = Query(default=None),
    handshake_scope: Callable[[], ContextManager[MatchHandshakeService]] = Depends(
        get_handshake_service_scope
    ),
    manager: MatchConnectionManager = Depends(get_connection_manager),
) -> None:
    def authorize() -> HandshakeGrant:
        with handshake_scope() as service:
            return service.authorize(token, match_id)

    try:
        grant = await run_in_threadpool(authorize)
        manager.reserve(grant.match_id, grant.user_id)
    except ApiError as error:
        await _reject(websocket, error)
        return

    try:
        await websocket.accept()
        manager.subscribe(grant.match_id, grant.user_id, websocket)
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    finally:
        manager.release(grant.match_id, grant.user_id, websocket)
