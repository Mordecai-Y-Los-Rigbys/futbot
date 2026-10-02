from fastapi import WebSocket

from app.errors import ApiError

MAX_CONNECTIONS_PER_USER_AND_MATCH = 5


class MatchConnectionManager:
    """Registro en memoria de las conexiones abiertas a /ws/matches/{id}.

    Cada conexión es un suscriptor independiente de la transmisión de un
    partido. Todos los métodos son síncronos (sin await), así que en un único
    event loop son atómicos entre sí: dos handshakes simultáneos no pueden
    pasarse el límite.

    Ciclo de vida de una conexión:
        reserve()   -> antes del accept; aplica el límite (429)
        subscribe() -> después del accept; recién ahí puede recibir mensajes
        release()   -> siempre al terminar (cierre normal, caída o error)

    Es estado de un solo proceso: si se corre con varios workers de uvicorn,
    cada uno tiene su propio registro (y el límite se aplica por worker).
    """

    def __init__(self) -> None:
        self._reserved: dict[tuple[int, int], int] = {}
        self._subscribers: dict[int, set[WebSocket]] = {}

    def reserve(self, match_id: int, user_id: int) -> None:
        key = (match_id, user_id)
        current = self._reserved.get(key, 0)
        if current >= MAX_CONNECTIONS_PER_USER_AND_MATCH:
            raise ApiError(
                429,
                None,
                "Superaste el máximo de conexiones simultáneas para este partido.",
            )
        self._reserved[key] = current + 1

    def subscribe(self, match_id: int, websocket: WebSocket) -> None:
        self._subscribers.setdefault(match_id, set()).add(websocket)

    def release(self, match_id: int, user_id: int, websocket: WebSocket) -> None:
        subs = self._subscribers.get(match_id)
        if subs is not None:
            subs.discard(websocket)
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

    def subscribers(self, match_id: int) -> list[WebSocket]:
        """Suscriptores actuales del partido. Lo usa la emisión de `tick`."""
        return list(self._subscribers.get(match_id, ()))