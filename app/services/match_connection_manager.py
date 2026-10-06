import asyncio
import logging

from fastapi import WebSocket

from app.errors import ApiError

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER_AND_MATCH = 5
WAIT_EXPIRED_CODE = 1000
WAIT_EXPIRED_REASON = "waitExpired"


class MatchConnectionManager:
    """Registro en memoria de las conexiones abiertas a /ws/matches/{id}.

    Cada conexión es un suscriptor independiente de la transmisión de un
    partido. reserve(), subscribe(), release(), count() y subscribers() son
    síncronos (sin await), así que en un único event loop son atómicos entre
    sí: dos handshakes simultáneos no pueden pasarse el límite. close_match()
    es la excepción: es async porque espera el cierre de cada socket. Toma una
    copia de los suscriptores antes de su primer await, así que tampoco ve
    estados intermedios.

    Ciclo de vida de una conexión:
        reserve()   -> antes del accept; aplica el límite (429)
        subscribe() -> después del accept; recién ahí puede recibir mensajes
        release()   -> siempre al terminar (cierre normal, caída o error)

    Es estado de un solo proceso: si se corre con varios workers de uvicorn,
    cada uno tiene su propio registro (y el límite se aplica por worker).
    """

    def __init__(self) -> None:
        self._reserved: dict[tuple[int, int], int] = {}
        self._subscribers: dict[int, dict[WebSocket, int]] = {}
        self._evicted: set[WebSocket] = set()

    def reserve(self, match_id: int, user_id: int) -> None:
        """Reserva un cupo de conexión para el usuario en el partido. Va antes del accept.

        Raises:
            ApiError 429: tooManyConnections, si ya tiene el máximo de conexiones abiertas.
        """

        key = (match_id, user_id)
        current = self._reserved.get(key, 0)
        if current >= MAX_CONNECTIONS_PER_USER_AND_MATCH:
            raise ApiError(
                429,
                "tooManyConnections",
                "Superaste el máximo de conexiones simultáneas para este partido.",
            )
        self._reserved[key] = current + 1

    def subscribe(self, match_id: int, user_id: int, websocket: WebSocket) -> None:
        """Suscribe la conexión a los ticks del partido. Va después del accept."""
        self._subscribers.setdefault(match_id, {})[websocket] = user_id

    def release(self, match_id: int, user_id: int, websocket: WebSocket) -> None:
        """Libera el cupo y la suscripción de una conexión que terminó.

        Lo llama siempre el endpoint al cerrar. Si la conexión ya había sido
        expulsada con evict(), no hace nada, para no liberar el cupo dos veces.
        """
        if websocket in self._evicted:  # ya liberado por evict()
            self._evicted.discard(websocket)
            return
        subs = self._subscribers.get(match_id)
        if subs is not None:
            subs.pop(websocket, None)
            if not subs:
                del self._subscribers[match_id]

        key = (match_id, user_id)
        current = self._reserved.get(key, 0)
        if current <= 1:
            self._reserved.pop(key, None)
        else:
            self._reserved[key] = current - 1

    def count(self, match_id: int, user_id: int) -> int:
        """Conexiones del usuario sobre el partido (incluye las que están
        terminando el handshake)."""
        return self._reserved.get((match_id, user_id), 0)

    def subscribers(self, match_id: int) -> list[tuple[WebSocket, int]]:
        """Suscriptores actuales del partido como (websocket, user_id)."""
        return list(self._subscribers.get(match_id, {}).items())

    def evict(self, match_id: int, user_id: int, websocket: WebSocket) -> None:
        subs = self._subscribers.get(match_id)
        if subs is None or websocket not in subs:
            return  # el endpoint ya lo liberó (o ya fue expulsado)
        self.release(match_id, user_id, websocket)
        self._evicted.add(websocket)

    async def close_match(
        self,
        match_id: int,
        code: int = WAIT_EXPIRED_CODE,
        reason: str = WAIT_EXPIRED_REASON,
    ) -> None:
        """Cierra todas las conexiones del partido (por defecto: espera vencida).

        Solo toca los suscriptores de `match_id`. Los cierres se hacen de forma
        concurrente sobre una copia de subscribers(); si un socket falla (por
        ejemplo, ya estaba cerrado) no impide cerrar a los demás, y el error se
        manda a un log. El release() lo hace el endpoint cuando recibe el
        disconnect, no este método.
        """
        sockets = [ws for ws, _user_id in self.subscribers(match_id)]
        results = await asyncio.gather(
            *(ws.close(code=code, reason=reason) for ws in sockets),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.debug(
                    "No se pudo cerrar un socket del partido %s: %r",
                    match_id,
                    result,
                )
