import asyncio
from typing import Callable, ContextManager

from fastapi import APIRouter, Depends, WebSocket
from starlette.concurrency import run_in_threadpool

from app.api.ws_league_deps import (
    get_league_participants_manager,
    get_participants_handshake_scope,
)
from app.errors import ApiError
from app.services.league_participants_handshake import (
    LeagueParticipantsHandshakeService,
    ParticipantsGrant,
)
from app.services.league_participants_manager import (
    LeagueParticipantsManager,
    ParticipantsConnection,
)

router = APIRouter(tags=["leagues"])


async def _reject(websocket: WebSocket, error: ApiError) -> None:
    await websocket.accept()
    await websocket.close(code=4000 + error.status_code, reason=error.code or "")


@router.websocket("/ws/leagues/{league_id}/participants")
async def league_participants_stream(
    websocket: WebSocket,
    league_id: str,
    handshake_scope: Callable[[], ContextManager[LeagueParticipantsHandshakeService]] = Depends(
        get_participants_handshake_scope
    ),
    manager: LeagueParticipantsManager = Depends(get_league_participants_manager),
) -> None:
    origin = websocket.headers.get("origin")
    session_id = websocket.cookies.get("session_id")

    def authorize() -> ParticipantsGrant:
        with handshake_scope() as service:
            return service.authorize(origin, session_id, league_id)

    try:
        grant = await run_in_threadpool(authorize)
        manager.reserve(grant.league_id, grant.user_id)
    except ApiError as error:
        await _reject(websocket, error)
        return

    connection: ParticipantsConnection | None = None
    sender: asyncio.Task | None = None
    try:
        await websocket.accept()
        connection = manager.subscribe(
            grant.league_id,
            grant.user_id,
            grant.session_id,
            websocket,
            grant.session_expires_at,
        )
        sender = asyncio.create_task(connection.run())
        # Los mensajes del cliente se ignoran.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    finally:
        if sender is not None:
            sender.cancel()
        manager.release(grant.league_id, grant.user_id, connection)
