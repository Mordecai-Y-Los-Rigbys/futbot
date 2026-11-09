import threading
import time
from contextlib import ExitStack, contextmanager

import pytest
from anyio import EndOfStream
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.ws_league_deps import get_league_participants_manager, get_participants_handshake_scope
from app.domain.league import LeagueStatus
from app.main import app
from app.services.league_participants_handshake import LeagueParticipantsHandshakeService
from app.services.league_participants_manager import LeagueParticipantsManager
from app.tests.unit.league_participants_fakes import CREATOR_ID, ORIGIN, FakeLeagues, FakeSessions

USER_ID = 8


@pytest.fixture()
def sessions():
    repo = FakeSessions()
    repo.add("creator-session", CREATOR_ID)
    repo.add("user-session", USER_ID)
    return repo


@pytest.fixture()
def leagues():
    repo = FakeLeagues()
    repo.add(1)  # pública, en preparación
    repo.add(2, private=True)
    repo.add(3)
    return repo


@pytest.fixture()
def manager(leagues):
    return LeagueParticipantsManager(leagues.get_state)


@pytest.fixture()
def client(sessions, leagues, manager):
    service = LeagueParticipantsHandshakeService([ORIGIN], sessions, leagues, leagues)

    @contextmanager
    def scope():
        yield service

    app.dependency_overrides[get_participants_handshake_scope] = lambda: scope
    app.dependency_overrides[get_league_participants_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def url(league_id=1):
    return f"/ws/leagues/{league_id}/participants"


def connect(client, league_id=1, session="user-session", origin=ORIGIN):
    """Abre la conexión (usar con `with`)."""
    headers = {} if origin is None else {"Origin": origin}
    client.cookies.clear()
    if session is not None:
        client.cookies.set("session_id", session)
    return client.websocket_connect(url(league_id), headers=headers)


def rejection(client, **kwargs) -> tuple[int, str]:
    """(close code, reason) del rechazo. Falla si llega algún mensaje antes."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with connect(client, **kwargs) as ws:
            message = ws.receive_text()
            pytest.fail(f"el rechazo no debería enviar mensajes: {message}")
    return exc.value.code, exc.value.reason


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def stays_silent(ws, seconds=0.5) -> bool:
    """True si no llega ningún mensaje (ni cierre) durante `seconds`."""
    received = []

    def _receive():
        try:
            received.append(ws.receive())
        except EndOfStream:
            pass

    t = threading.Thread(target=_receive, daemon=True)
    t.start()
    t.join(seconds)
    return not received


def ids(message) -> list[int]:
    return [p["id"] for p in message["participants"]]


def closing(ws) -> tuple[int, str]:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_text()
    return exc.value.code, exc.value.reason


# --- un test por cada cierre del handshake ------------------------------------


@pytest.mark.parametrize("origin", [None, "http://evil.com"])
def test_origin_not_allowed_is_4403(client, origin):
    assert rejection(client, origin=origin) == (4403, "originNotAllowed")


@pytest.mark.parametrize("session", [None, "no-existe"])
def test_session_invalid_is_4401(client, session):
    assert rejection(client, session=session) == (4401, "sessionInvalid")


@pytest.mark.parametrize("league_id", ["999", "0", "abc", "1.5", "2147483648"])
def test_league_not_found_or_invalid_id_is_4404(client, league_id):
    assert rejection(client, league_id=league_id) == (4404, "leagueNotFound")


def test_private_league_without_access_is_4403_league_access_required(client):
    assert rejection(client, league_id=2) == (4403, "leagueAccessRequired")


@pytest.mark.parametrize(
    "status", [LeagueStatus.started, LeagueStatus.cancelled, LeagueStatus.finished]
)
def test_league_not_in_preparation_is_4409_without_messages(client, leagues, status):
    leagues.set_status(1, status)
    assert rejection(client) == (4409, "leagueNotInPreparation")


def test_sixth_connection_is_4429_and_a_slot_frees_on_close(client, manager):
    with ExitStack() as stack:
        sockets = [stack.enter_context(connect(client)) for _ in range(5)]
        assert manager.count(1, USER_ID) == 5

        assert rejection(client) == (4429, "tooManyConnections")

        sockets[0].close()
        assert wait_until(lambda: manager.count(1, USER_ID) == 4)
        with connect(client):
            assert manager.count(1, USER_ID) == 5


def test_limit_is_per_user(client, manager):
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(client))
        with connect(client, session="creator-session") as ws:
            assert ws.receive_json()["type"] == "leagueParticipants"


# --- orden de precedencia -----------------------------------------------------


def test_precedence_origin_beats_everything(client):
    assert rejection(client, origin=None, session=None, league_id="abc") == (
        4403,
        "originNotAllowed",
    )


def test_precedence_session_beats_league(client):
    assert rejection(client, session="no-existe", league_id="999") == (4401, "sessionInvalid")


def test_precedence_league_not_found_beats_access(client):
    assert rejection(client, league_id="999") == (4404, "leagueNotFound")


def test_precedence_access_beats_state(client, leagues):
    leagues.set_status(2, LeagueStatus.started)
    assert rejection(client, league_id=2) == (4403, "leagueAccessRequired")


def test_precedence_state_beats_connection_limit(client, leagues, manager):
    for _ in range(5):
        manager.reserve(1, USER_ID)
    leagues.set_status(1, LeagueStatus.started)
    assert rejection(client) == (4409, "leagueNotInPreparation")


def test_rejected_handshake_leaves_no_registration(client, manager):
    rejection(client, session="no-existe")
    assert manager.subscribers(1) == [] and manager._reserved == {}


# --- conexión aceptada --------------------------------------------------------


def test_public_league_opens_for_any_user_with_the_current_list_first(client):
    with connect(client) as ws:
        assert ws.receive_json() == {
            "type": "leagueParticipants",
            "leagueStatus": "preparation",
            "participants": [{"id": CREATOR_ID, "username": "user7", "name": "club7", "avatar": 1}],
        }


@pytest.mark.parametrize("who", ["creator", "participant", "unlocked"])
def test_private_league_opens_for_creator_participant_or_unlocked_session(client, leagues, who):
    session = "creator-session" if who == "creator" else "user-session"
    if who == "participant":
        leagues.join(2, USER_ID)
    if who == "unlocked":
        leagues.unlock("user-session", 2)
    with connect(client, league_id=2, session=session) as ws:
        assert ws.receive_json()["leagueStatus"] == "preparation"


def test_incoming_messages_are_ignored_and_do_not_close(client, manager):
    with connect(client) as ws:
        ws.receive_json()  # inicial
        ws.send_text("hola")
        ws.send_bytes(b"\x00\x01")
        ws.send_json({"type": "leagueParticipants"})
        assert stays_silent(ws)
        assert manager.count(1, USER_ID) == 1


def test_closing_releases_the_slot_and_the_subscription(client, manager):
    with connect(client) as ws:
        ws.receive_json()
        assert len(manager.subscribers(1)) == 1
    assert wait_until(lambda: manager.subscribers(1) == [] and manager.count(1, USER_ID) == 0)


# --- cambios mientras la conexión está abierta --------------------------------


def test_join_and_leave_send_the_full_list(client, leagues, manager):
    with connect(client) as ws:
        assert ids(ws.receive_json()) == [CREATOR_ID]

        leagues.join(1, 9)
        manager.participants_changed(1)
        assert ids(ws.receive_json()) == [CREATOR_ID, 9]

        leagues.leave(1, 9)
        manager.participants_changed(1)
        assert ids(ws.receive_json()) == [CREATOR_ID]


def test_messages_of_one_league_do_not_reach_another(client, leagues, manager):
    with connect(client, league_id=1) as mine, connect(client, league_id=3) as other:
        mine.receive_json()
        other.receive_json()
        leagues.join(1, 9)
        manager.participants_changed(1)
        assert ids(mine.receive_json()) == [CREATOR_ID, 9]
        assert stays_silent(other)


@pytest.mark.parametrize(
    "status, reason",
    [(LeagueStatus.started, "leagueStarted"), (LeagueStatus.cancelled, "leagueCancelled")],
)
def test_league_start_or_cancel_sends_a_last_message_and_closes_1000(
    client, leagues, manager, status, reason
):
    with connect(client) as ws:
        ws.receive_json()
        leagues.set_status(1, status)
        manager.league_status_changed(1)
        assert ws.receive_json()["leagueStatus"] == status.value
        assert closing(ws) == (1000, reason)
    assert wait_until(lambda: manager.count(1, USER_ID) == 0)
    # Una conexión nueva a la liga ya iniciada se rechaza sin mensajes
    assert rejection(client) == (4409, "leagueNotInPreparation")


def test_session_end_closes_with_4401_session_ended(client, manager):
    with connect(client) as ws:
        ws.receive_json()
        manager.session_ended("user-session")
        assert closing(ws) == (4401, "sessionEnded")


def test_leaving_the_league_does_not_close_the_connection(client, leagues, manager):
    leagues.join(1, USER_ID)
    with connect(client) as ws:
        ws.receive_json()
        leagues.leave(1, USER_ID)
        manager.participants_changed(1)
        assert ids(ws.receive_json()) == [CREATOR_ID]
        assert stays_silent(ws)
        assert manager.count(1, USER_ID) == 1
