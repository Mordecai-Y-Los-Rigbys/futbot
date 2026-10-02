from typing import Callable, ContextManager

from fastapi import APIRouter, Depends, Query, WebSocket
from starlette.concurrency import run_in_threadpool

from app.api.ws_deps import get_connection_manager, get_handshake_service_scope
from app.errors import ApiError
from app.services.match_connection_manager import MatchConnectionManager
from app.services.match_handshake_service import HandshakeGrant, MatchHandshakeService

router = APIRouter(tags=["matches"])


async def _deny(websocket: WebSocket, error: ApiError) -> None:
    """Rechaza el handshake con una respuesta HTTP, antes del upgrade.

    Los exception handlers de FastAPI no aplican a WebSockets, por eso se
    convierte a mano; el formato sale de ApiError.to_response().
    """
    await websocket.send_denial_response(error.to_response())


@router.websocket("/ws/matches/{match_id}")
async def match_stream(
    websocket: WebSocket,
    match_id: str,  # str y no int: un id inválido tiene que dar 403, no cerrar el socket
    token: str | None = Query(default=None),
    handshake_scope: Callable[[], ContextManager[MatchHandshakeService]] = Depends(
        get_handshake_service_scope
    ),
    manager: MatchConnectionManager = Depends(get_connection_manager),
) -> None:
    def authorize() -> HandshakeGrant:
        # Sesión de DB de vida corta: se cierra antes del accept.
        with handshake_scope() as service:
            return service.authorize(token, match_id)

    try:
        grant = await run_in_threadpool(authorize)
        manager.reserve(grant.match_id, grant.user_id)  # 429 si supera el límite
    except ApiError as error:
        await _deny(websocket, error)
        return

    try:
        await websocket.accept()
        manager.subscribe(grant.match_id, websocket)
        # Los mensajes entrantes se ignoran; solo se espera el cierre.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    finally:
        manager.release(grant.match_id, grant.user_id, websocket)