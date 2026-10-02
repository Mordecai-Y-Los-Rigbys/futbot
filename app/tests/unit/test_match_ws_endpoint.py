import threading
import time
from datetime import timedelta
from contextlib import ExitStack, contextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse
from anyio import EndOfStream

from app.api.ws_deps import get_connection_manager, get_handshake_service_scope
from app.main import app
from app.services import match_handshake_service
from app.services.match_connection_manager import MatchConnectionManager
from app.services.match_handshake_service import MatchHandshakeService
from app.tests.unit.match_ws_fakes import NOW, FakeMatchRepo, FakeTokenRepo


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(match_handshake_service, "_utcnow", lambda: NOW)


@pytest.fixture()
def tokens():
    repo = FakeTokenRepo()
    repo.add("tok", user_id=7, match_id=1)
    return repo


@pytest.fixture()
def matches():
    repo = FakeMatchRepo()
    repo.add(1)
    return repo


@pytest.fixture()
def manager():
    return MatchConnectionManager()


@pytest.fixture()
def client(tokens, matches, manager):
    service = MatchHandshakeService(tokens, matches)

    @contextmanager
    def scope():
        yield service

    app.dependency_overrides[get_handshake_service_scope] = lambda: scope
    app.dependency_overrides[get_connection_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def url(match_id=1, token="tok"):
    return f"/ws/matches/{match_id}" + ("" if token is None else f"?token={token}")


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def denied(client, path) -> WebSocketDenialResponse:
    with pytest.raises(WebSocketDenialResponse) as exc:
        with client.websocket_connect(path):
            pass
    return exc.value


def stays_silent(ws, seconds=0.5) -> bool:
    """True si no llega ningún mensaje (ni cierre) durante `seconds`."""
    received = []

    def _receive():
        try:
            received.append(ws.receive())
        except EndOfStream:
            pass  # la conexión se cerró al terminar el test: no es un mensaje

    t = threading.Thread(target=_receive, daemon=True)
    t.start()
    t.join(seconds)
    return not received


# --- handshake aceptado --------------------------------------------------------

def test_valid_token_opens_the_connection(client, manager):
    with client.websocket_connect(url()):
        assert manager.count(1, 7) == 1


def test_connection_is_registered_as_subscriber(client, manager):
    with client.websocket_connect(url()):
        assert wait_until(lambda: len(manager.subscribers(1)) == 1)


# --- handshake rechazado (HTTP antes del upgrade) --------------------------------

@pytest.mark.parametrize("token", [None, "", "no-existe", "x" * 100])
def test_missing_or_invalid_token_is_401(client, manager, token):
    resp = denied(client, url(token=token))
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    assert resp.json()["message"]
    assert manager.count(1, 7) == 0


def test_expired_token_is_401(client, tokens):
    tokens.add("viejo", match_id=1, expires_at=NOW - timedelta(seconds=1))
    assert denied(client, url(token="viejo")).status_code == 401


def test_token_of_another_match_is_403(client, matches):
    matches.add(2)
    resp = denied(client, url(match_id=2))
    assert resp.status_code == 403
    assert resp.json()["code"] is None


@pytest.mark.parametrize("match_id", ["abc", "1.5", "0", "99999999999999999999"])
def test_garbage_match_id_is_rejected_over_http(client, match_id):
    assert denied(client, url(match_id=match_id)).status_code == 403


def test_nonexistent_match_is_404(client, tokens):
    tokens.add("huerfano", match_id=5)
    resp = denied(client, url(match_id=5, token="huerfano"))
    assert resp.status_code == 404
    assert resp.json()["code"] is None


def test_finished_match_is_409_match_finished(client, matches):
    matches.add(1, finished=True)
    resp = denied(client, url())
    assert resp.status_code == 409
    assert resp.json()["code"] == "matchFinished"


def test_rejected_handshake_leaves_no_registration(client, manager):
    denied(client, url(token="no-existe"))
    assert manager.subscribers(1) == []
    assert manager._reserved == {}


# --- reconexión y conexiones múltiples ------------------------------------------------

def test_same_token_can_reconnect_after_closing(client, manager):
    with client.websocket_connect(url()):
        pass
    with client.websocket_connect(url()):
        assert manager.count(1, 7) == 1


def test_simultaneous_connections_with_the_same_token(client, manager):
    with client.websocket_connect(url()), client.websocket_connect(url()):
        assert manager.count(1, 7) == 2
        assert wait_until(lambda: len(manager.subscribers(1)) == 2)


def test_sixth_simultaneous_connection_is_429_and_a_slot_frees_on_close(client, manager):
    with ExitStack() as stack:
        sockets = [stack.enter_context(client.websocket_connect(url())) for _ in range(5)]
        assert manager.count(1, 7) == 5

        resp = denied(client, url())
        assert resp.status_code == 429
        assert resp.json()["code"] is None
        assert manager.count(1, 7) == 5

        sockets[0].close()
        assert wait_until(lambda: manager.count(1, 7) == 4)
        with client.websocket_connect(url()):
            assert manager.count(1, 7) == 5


def test_limit_does_not_affect_other_users(client, tokens, manager):
    tokens.add("otro", user_id=8, match_id=1)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(client.websocket_connect(url()))
        with client.websocket_connect(url(token="otro")):
            assert manager.count(1, 8) == 1


# --- silencio y mensajes entrantes --------------------------------------------------------

def test_waiting_for_the_rival_the_client_stays_connected_and_receives_nothing(client, manager):
    with client.websocket_connect(url()) as ws:
        assert stays_silent(ws)
        assert manager.count(1, 7) == 1


def test_incoming_messages_are_ignored(client, manager, matches):
    states_before = dict(matches.states)
    with client.websocket_connect(url()) as ws:
        ws.send_text("hola")
        ws.send_bytes(b"\x00\x01")
        ws.send_json({"type": "pause"})
        assert stays_silent(ws)  # ni respuesta ni cierre
        assert manager.count(1, 7) == 1
    assert matches.states == states_before


# --- cierre y limpieza -----------------------------------------------------------------------------

def test_closing_the_connection_releases_the_subscription(client, manager):
    with client.websocket_connect(url()):
        assert wait_until(lambda: len(manager.subscribers(1)) == 1)
    assert manager.subscribers(1) == []
    assert manager.count(1, 7) == 0


def test_disconnect_does_not_change_the_match(client, matches):
    states_before = dict(matches.states)
    with client.websocket_connect(url()):
        pass
    assert matches.states == states_before
    assert matches.states[1].finished is False


def test_match_stream_reaches_open_and_late_connections(client, manager):
    """Contrato con el ticket de `tick`: quien emite toma los suscriptores del
    manager. La conexión ya abierta recibe sin reconectar; quien se conecta
    después recibe solo desde ese momento (sin replay)."""

    def emit(ws, payload):
        (subscriber,) = manager.subscribers(1)[:1]
        ws.portal.call(subscriber.send_json, payload)

    with client.websocket_connect(url()) as first:
        assert wait_until(lambda: len(manager.subscribers(1)) == 1)
        emit(first, {"n": 1})
        assert first.receive_json() == {"n": 1}

        with client.websocket_connect(url()) as late:
            assert wait_until(lambda: len(manager.subscribers(1)) == 2)
            for sub in manager.subscribers(1):
                first.portal.call(sub.send_json, {"n": 2})
            assert first.receive_json() == {"n": 2}
            assert late.receive_json() == {"n": 2}  # el 1 no se le reenvía