import asyncio
from typing import Callable, ContextManager

from fastapi import APIRouter, Depends, WebSocket
from starlette.concurrency import run_in_threadpool

from app.api.ws_league_deps import (
    get_fixture_handshake_scope,
    get_league_fixture_manager,
    get_league_next_match_manager,
    get_league_participants_manager,
    get_league_ranking_manager,
    get_next_match_handshake_scope,
    get_participants_handshake_scope,
    get_ranking_handshake_scope,
)
from app.errors import ApiError
from app.services.league_channel_handshake import LeagueChannelGrant, LeagueChannelHandshakeService
from app.services.league_channel_manager import LeagueChannelConnection, LeagueChannelManager

router = APIRouter(tags=["leagues"])

HandshakeScope = Callable[[], ContextManager[LeagueChannelHandshakeService]]


async def _reject(websocket: WebSocket, error: ApiError) -> None:
    await websocket.accept()
    await websocket.close(code=4000 + error.status_code, reason=error.code or "")


async def _stream(
    websocket: WebSocket,
    league_id: str,
    handshake_scope: HandshakeScope,
    manager: LeagueChannelManager,
) -> None:
    origin = websocket.headers.get("origin")
    session_id = websocket.cookies.get("session_id")

    def authorize() -> LeagueChannelGrant:
        with handshake_scope() as service:
            return service.authorize(origin, session_id, league_id)

    try:
        grant = await run_in_threadpool(authorize)
        manager.reserve(grant.league_id, grant.user_id)
    except ApiError as error:
        await _reject(websocket, error)
        return

    connection: LeagueChannelConnection | None = None
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


@router.websocket("/ws/leagues/{league_id}/participants")
async def league_participants_stream(
    websocket: WebSocket,
    league_id: str,
    handshake_scope: HandshakeScope = Depends(get_participants_handshake_scope),
    manager: LeagueChannelManager = Depends(get_league_participants_manager),
) -> None:
    await _stream(websocket, league_id, handshake_scope, manager)


@router.websocket("/ws/leagues/{league_id}/fixture")
async def league_fixture_stream(
    websocket: WebSocket,
    league_id: str,
    handshake_scope: HandshakeScope = Depends(get_fixture_handshake_scope),
    manager: LeagueChannelManager = Depends(get_league_fixture_manager),
) -> None:
    await _stream(websocket, league_id, handshake_scope, manager)


@router.websocket("/ws/leagues/{league_id}/ranking")
async def league_ranking_stream(
    websocket: WebSocket,
    league_id: str,
    handshake_scope: HandshakeScope = Depends(get_ranking_handshake_scope),
    manager: LeagueChannelManager = Depends(get_league_ranking_manager),
) -> None:
    await _stream(websocket, league_id, handshake_scope, manager)


@router.websocket("/ws/leagues/{league_id}/matches/next")
async def league_next_match_stream(
    websocket: WebSocket,
    league_id: str,
    handshake_scope: HandshakeScope = Depends(get_next_match_handshake_scope),
    manager: LeagueChannelManager = Depends(get_league_next_match_manager),
) -> None:
    await _stream(websocket, league_id, handshake_scope, manager)
