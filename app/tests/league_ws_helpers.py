import threading
import time

import pytest
from anyio import ClosedResourceError, EndOfStream
from starlette.websockets import WebSocketDisconnect

ORIGIN = "http://localhost:5173"


def connect(client, url, origin=ORIGIN):
    """Abre la conexión (usar con `with`)."""
    headers = {} if origin is None else {"Origin": origin}
    return client.websocket_connect(url, headers=headers)


def rejection(client, url, origin=ORIGIN) -> tuple[int, str]:
    """(code, reason) del rechazo. Falla si llega algún mensaje antes."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with connect(client, url, origin) as ws:
            message = ws.receive_text()
            pytest.fail(f"el rechazo no debería enviar mensajes: {message}")
    return exc.value.code, exc.value.reason


def closing(ws) -> tuple[int, str]:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_text()
    return exc.value.code, exc.value.reason


def stays_silent(ws, seconds=0.5) -> bool:
    """True si no llega ningún mensaje (ni cierre) durante `seconds`."""
    received = []

    def _receive():
        try:
            received.append(ws.receive())
        except (EndOfStream, ClosedResourceError):
            pass  # el test terminó y se cerró la conexión

    t = threading.Thread(target=_receive, daemon=True)
    t.start()
    t.join(seconds)
    return not received


def wait_until(predicate, timeout=2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False