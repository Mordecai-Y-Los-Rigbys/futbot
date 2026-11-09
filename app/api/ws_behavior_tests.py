import asyncio
from typing import Callable, ContextManager

from fastapi import APIRouter, Depends, Query, WebSocket
from starlette.concurrency import run_in_threadpool

from app.api.ws_behavior_test_deps import (
    get_behavior_test_handshake_scope,
    get_behavior_test_runner,
    get_behavior_test_slots,
)
from app.errors import ApiError
from app.services.behavior_test_handshake import BehaviorTestGrant, BehaviorTestHandshakeService
from app.services.behavior_test_runner import BehaviorTestRunner
from app.services.behavior_test_slots import BehaviorTestSlots

router = APIRouter(tags=["behaviors"])


async def _reject(websocket: WebSocket, error: ApiError) -> None:
    """Como en el partido: se acepta el upgrade y se cierra con 4000 + status."""
    await websocket.accept()
    await websocket.close(code=4000 + error.status_code, reason=error.code or "")


@router.websocket("/ws/behaviors/{behavior_id}/test")
async def behavior_test_stream(
    websocket: WebSocket,
    behavior_id: str,
    token: str | None = Query(default=None),
    handshake_scope: Callable[[], ContextManager[BehaviorTestHandshakeService]] = Depends(
        get_behavior_test_handshake_scope
    ),
    slots: BehaviorTestSlots = Depends(get_behavior_test_slots),
    runner: BehaviorTestRunner = Depends(get_behavior_test_runner),
) -> None:
    def authorize() -> BehaviorTestGrant:
        with handshake_scope() as service:
            return service.authorize(token, behavior_id)

    try:
        grant = await run_in_threadpool(authorize)
        slots.reserve(grant.user_id)
    except ApiError as error:
        await _reject(websocket, error)
        return

    test = None
    try:
        await websocket.accept()
        # La conexión es la prueba: arranca ahora y termina cuando se cierra.
        test = asyncio.create_task(
            runner.run(websocket, grant.behavior_id, grant.club_1, grant.club_2)
        )
        while True:
            message = await websocket.receive()  # lo que mande el cliente se ignora
            if message["type"] == "websocket.disconnect":
                break
    finally:
        if test is not None:
            test.cancel()
        slots.release(grant.user_id)
