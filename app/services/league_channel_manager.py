import asyncio
import json
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket

from app.domain.league import LeagueStatus
from app.errors import ApiError

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER_AND_LEAGUE = 5
LEAGUE_CLOSED_CODE = 1000
SESSION_ENDED_CODE = 4401
SESSION_ENDED_REASON = "sessionEnded"
LEAGUE_NOT_FOUND_CODE = 4404
LEAGUE_NOT_FOUND_REASON = "leagueNotFound"
INTERNAL_ERROR_CODE = 1011

# Devuelve el estado del canal (con un atributo `status`) o None si la liga no existe.
LoadState = Callable[[int], Any]


@dataclass(frozen=True)
class LeagueChannelSpec:
    """Lo que cambia entre canales de liga."""

    # Recibe el estado y el user_id de la conexión
    build_payload: Callable[[Any, int], dict]
    # Estados en los que se envía el último mensaje y se cierra con 1000 + reason.
    close_reasons: Mapping[LeagueStatus, str]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeagueChannelConnection:
    """Una conexión abierta a un canal de liga. Se crea dentro del event loop."""

    def __init__(
        self,
        league_id: int,
        user_id: int,
        session_id: str,
        websocket: WebSocket,
        load_state: LoadState,
        spec: LeagueChannelSpec,
        session_expires_at: datetime | None = None,
    ) -> None:
        self.league_id = league_id
        self.user_id = user_id
        self.session_id = session_id
        self.websocket = websocket
        self._load_state = load_state
        self._spec = spec
        self._session_expires_at = session_expires_at
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._stale = True  # al conectar se envía el estado actual
        self._session_ended = False

    def notify(self) -> None:
        """Pide reenviar el estado. Se puede llamar desde cualquier hilo."""
        self._call_in_loop(self._mark_stale)

    def end_session(self) -> None:
        """Pide cerrar con 4401 / sessionEnded. Se puede llamar desde cualquier hilo."""
        self._call_in_loop(self._mark_session_ended)

    def _call_in_loop(self, callback: Callable[[], None]) -> None:
        try:
            self._loop.call_soon_threadsafe(callback)
        except RuntimeError:
            pass  # el loop ya terminó

    def _mark_stale(self) -> None:
        self._stale = True
        self._wake.set()

    def _mark_session_ended(self) -> None:
        self._session_ended = True
        self._wake.set()

    def _seconds_until_expiry(self) -> float | None:
        if self._session_expires_at is None:
            return None
        return (self._session_expires_at - _utcnow()).total_seconds()

    async def _close(self, code: int, reason: str) -> None:
        try:
            await self.websocket.close(code=code, reason=reason)
        except Exception:
            pass

    async def run(self) -> None:
        """Envía el estado completo cada vez que cambia, hasta cerrar. Nunca lanza.

        El cupo lo libera el endpoint al recibir el disconnect.
        """
        try:
            while True:
                remaining = self._seconds_until_expiry()
                if self._session_ended or (remaining is not None and remaining <= 0):
                    await self._close(SESSION_ENDED_CODE, SESSION_ENDED_REASON)
                    return

                if self._stale:
                    self._stale = False
                    state = await run_in_threadpool(self._load_state, self.league_id)
                    if self._session_ended:
                        continue
                    if state is None:
                        await self._close(LEAGUE_NOT_FOUND_CODE, LEAGUE_NOT_FOUND_REASON)
                        return
                    payload = self._spec.build_payload(state, self.user_id)
                    await self.websocket.send_text(json.dumps(payload, separators=(",", ":")))
                    reason = self._spec.close_reasons.get(state.status)
                    if reason is not None:
                        await self._close(LEAGUE_CLOSED_CODE, reason)
                        return
                    continue

                # Sin await entre el chequeo de arriba y el clear: no se pierden avisos.
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), remaining)
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Fin de la conexión a la liga %s", self.league_id, exc_info=True)
            await self._close(INTERNAL_ERROR_CODE, "")


class LeagueChannelManager:
    """Registro en memoria de las conexiones a un canal de liga.

    Ciclo de vida de una conexión:
        reserve()   -> antes del accept; aplica el límite (429)
        subscribe() -> después del accept; la conexión lee el estado recién después
        release()   -> siempre al terminar
    """

    def __init__(self, load_state: LoadState, spec: LeagueChannelSpec) -> None:
        self._load_state = load_state
        self._spec = spec
        self._lock = threading.Lock()  # los avisos llegan desde el threadpool
        self._reserved: dict[tuple[int, int], int] = {}
        self._subscribers: dict[int, set[LeagueChannelConnection]] = {}

    def reserve(self, league_id: int, user_id: int) -> None:
        """Reserva un cupo de conexión.

        Raises:
            ApiError 429: tooManyConnections, si el usuario ya tiene el máximo abierto.
        """
        key = (league_id, user_id)
        with self._lock:
            current = self._reserved.get(key, 0)
            if current >= MAX_CONNECTIONS_PER_USER_AND_LEAGUE:
                raise ApiError(
                    429,
                    "tooManyConnections",
                    "Superaste el máximo de conexiones simultáneas para esta liga.",
                )
            self._reserved[key] = current + 1

    def subscribe(
        self,
        league_id: int,
        user_id: int,
        session_id: str,
        websocket: WebSocket,
        session_expires_at: datetime | None = None,
    ) -> LeagueChannelConnection:
        connection = LeagueChannelConnection(
            league_id, user_id, session_id, websocket,
            self._load_state, self._spec, session_expires_at,
        )
        with self._lock:
            self._subscribers.setdefault(league_id, set()).add(connection)
        return connection

    def release(
        self, league_id: int, user_id: int, connection: LeagueChannelConnection | None = None
    ) -> None:
        """Libera el cupo y la suscripción. `connection` es None si el accept falló."""
        with self._lock:
            if connection is not None:
                subs = self._subscribers.get(league_id)
                if subs is not None:
                    subs.discard(connection)
                    if not subs:
                        del self._subscribers[league_id]

            key = (league_id, user_id)
            current = self._reserved.get(key, 0)
            if current <= 1:
                self._reserved.pop(key, None)
            else:
                self._reserved[key] = current - 1

    def count(self, league_id: int, user_id: int) -> int:
        with self._lock:
            return self._reserved.get((league_id, user_id), 0)

    def subscribers(self, league_id: int) -> list[LeagueChannelConnection]:
        with self._lock:
            return list(self._subscribers.get(league_id, ()))

    def notify(self, league_id: int) -> None:
        """El estado del canal cambió. Llamar después del commit."""
        for connection in self.subscribers(league_id):
            connection.notify()

    def session_ended(self, session_id: str) -> None:
        """Log-out: cierra las conexiones de la sesión con 4401. El vencimiento
        no necesita aviso, cada conexión cierra sola en `expires_at`."""
        with self._lock:
            connections = [
                c for subs in self._subscribers.values() for c in subs if c.session_id == session_id
            ]
        for connection in connections:
            connection.end_session()