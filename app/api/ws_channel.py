import asyncio
from datetime import datetime

from fastapi import WebSocket

from app.errors import ApiError
from app.services.league_channel_manager import LeagueChannelConnection, LeagueChannelManager


async def reject(websocket: WebSocket, error: ApiError) -> None:
    await websocket.accept()
    await websocket.close(code=4000 + error.status_code, reason=error.code or "")


async def serve(
    websocket: WebSocket,
    manager: LeagueChannelManager,
    key: int,
    user_id: int,
    session_id: str,
    session_expires_at: datetime,
) -> None:
    """Acepta una conexión con el cupo ya reservado en `manager` y envía el estado
    hasta que se cierre. `key` es la clave con la que el manager la registra."""
    connection: LeagueChannelConnection | None = None
    sender: asyncio.Task | None = None
    try:
        await websocket.accept()
        connection = manager.subscribe(key, user_id, session_id, websocket, session_expires_at)
        sender = asyncio.create_task(connection.run())
        # Los mensajes del cliente se ignoran.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    finally:
        if sender is not None:
            sender.cancel()
        manager.release(key, user_id, connection)
