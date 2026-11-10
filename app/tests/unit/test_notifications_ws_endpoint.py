from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.ws_notification_deps import (
    get_notifications_handshake_scope,
    get_notifications_manager,
)
from app.main import app
from app.services.notifications_channel import NotificationsHandshakeService, NotificationsManager
from app.tests.league_ws_helpers import closing, connect, rejection, stays_silent, wait_until
from app.tests.unit.league_participants_fakes import ORIGIN, FakeSessions
from app.tests.unit.notification_fakes import (
    FakeNotifications,
    league_notification,
    match_notification,
)

USER_ID = 8
OTHER_ID = 9
URL = "/ws/notifications"


@pytest.fixture()
def sessions():
    repo = FakeSessions()
    repo.add("user-session", USER_ID)
    repo.add("other-session", OTHER_ID)
    return repo


@pytest.fixture()
def notifications():
    return FakeNotifications()


@pytest.fixture()
def manager(notifications):
    return NotificationsManager(notifications.get_state)


@pytest.fixture()
def client(sessions, manager):
    service = NotificationsHandshakeService([ORIGIN], sessions)

    @contextmanager
    def scope():
        yield service

    app.dependency_overrides[get_notifications_handshake_scope] = lambda: scope
    app.dependency_overrides[get_notifications_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, session="user-session"):
    client.cookies.clear()
    if session is not None:
        client.cookies.set("session_id", session)
    return client


def ids(message) -> list[int]:
    return [n["id"] for n in message["notifications"]]


# --- handshake ----------------------------------------------------------------


@pytest.mark.parametrize("origin", [None, "http://evil.com"])
def test_origin_not_allowed_is_4403(client, origin):
    assert rejection(login(client), URL, origin=origin) == (4403, "originNotAllowed")


@pytest.mark.parametrize("session", [None, "no-existe"])
def test_session_invalid_is_4401(client, session):
    assert rejection(login(client, session), URL) == (4401, "sessionInvalid")


def test_expired_session_is_4401(client, sessions):
    sessions.sessions.pop("user-session")  # get_valid no devuelve las vencidas
    assert rejection(login(client), URL) == (4401, "sessionInvalid")


def test_sixth_connection_is_4429_and_the_others_keep_receiving(client, notifications, manager):
    api = login(client)
    with ExitStack() as stack:
        sockets = [stack.enter_context(connect(api, URL)) for _ in range(5)]
        for ws in sockets:
            ws.receive_json()

        assert rejection(api, URL) == (4429, "tooManyConnections")

        notifications.add(USER_ID, match_notification(1))
        manager.notifications_changed([USER_ID])
        for ws in sockets:
            assert ids(ws.receive_json()) == [1]


def test_the_limit_is_per_user(client):
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(login(client), URL)).receive_json()
        with connect(login(client, "other-session"), URL) as ws:
            assert ws.receive_json()["type"] == "notifications"


def test_precedence_origin_beats_session(client):
    assert rejection(login(client, None), URL, origin=None) == (4403, "originNotAllowed")


def test_precedence_session_beats_connection_limit(client, manager):
    for _ in range(5):
        manager.reserve(USER_ID, USER_ID)
    assert rejection(login(client, "no-existe"), URL) == (4401, "sessionInvalid")


def test_rejected_handshake_leaves_no_registration(client, manager):
    rejection(login(client, "no-existe"), URL)
    assert manager.subscribers(USER_ID) == [] and manager._reserved == {}


# --- mensaje inicial ----------------------------------------------------------


def test_the_current_state_arrives_on_connect(client, notifications):
    notifications.add(USER_ID, match_notification(1, minute=0))
    notifications.add(USER_ID, match_notification(2, minute=5, seen=True))
    with connect(login(client), URL) as ws:
        message = ws.receive_json()
    assert (message["type"], message["new"]) == ("notifications", True)
    assert ids(message) == [2, 1]


def test_without_notifications_the_message_is_empty(client):
    with connect(login(client), URL) as ws:
        assert ws.receive_json() == {"type": "notifications", "new": False, "notifications": []}


def test_only_the_10_most_recent_arrive_newest_first(client, notifications):
    for i in range(1, 13):
        notifications.add(USER_ID, match_notification(i, minute=i))
    with connect(login(client), URL) as ws:
        assert ids(ws.receive_json()) == list(range(12, 2, -1))


def test_same_date_is_ordered_by_id_descending(client, notifications):
    notifications.add(USER_ID, match_notification(1))
    notifications.add(USER_ID, league_notification(2))
    with connect(login(client), URL) as ws:
        assert ids(ws.receive_json()) == [2, 1]


def test_an_unseen_one_outside_the_10_sent_makes_new_true(client, notifications):
    notifications.add(USER_ID, match_notification(1, minute=0))
    for i in range(2, 12):
        notifications.add(USER_ID, match_notification(i, minute=i, seen=True))
    with connect(login(client), URL) as ws:
        message = ws.receive_json()
    assert 1 not in ids(message)
    assert all(n["seen"] for n in message["notifications"])
    assert message["new"] is True


def test_reconnecting_sends_only_the_current_state(client, notifications):
    notifications.add(USER_ID, match_notification(1))
    api = login(client)
    with connect(api, URL) as ws:
        ws.receive_json()
    notifications.mark_all_seen(USER_ID)
    with connect(api, URL) as ws:
        message = ws.receive_json()
        assert message["new"] is False
        assert stays_silent(ws)


# --- cambios con la conexión abierta ------------------------------------------


def test_a_new_notification_sends_the_full_state(client, notifications, manager):
    notifications.add(USER_ID, match_notification(1, minute=0))
    with connect(login(client), URL) as ws:
        ws.receive_json()
        notifications.add(USER_ID, match_notification(2, minute=5))
        manager.notifications_changed([USER_ID])
        message = ws.receive_json()
        assert ids(message) == [2, 1]
        assert message["new"] is True


def test_match_and_league_notifications_together_send_a_single_message(
    client, notifications, manager
):
    with connect(login(client), URL) as ws:
        ws.receive_json()
        notifications.add(USER_ID, match_notification(1))
        notifications.add(USER_ID, league_notification(2))
        manager.notifications_changed([USER_ID])
        message = ws.receive_json()
        assert [n["kind"] for n in message["notifications"]] == ["leagueFinished", "matchFinished"]
        assert stays_silent(ws)


def test_marking_them_seen_sends_the_updated_state(client, notifications, manager):
    notifications.add(USER_ID, match_notification(1))
    with connect(login(client), URL) as ws:
        assert ws.receive_json()["new"] is True
        notifications.mark_all_seen(USER_ID)
        manager.notifications_changed([USER_ID])
        message = ws.receive_json()
        assert message["new"] is False
        assert message["notifications"][0]["seen"] is True


def test_users_who_are_not_notified_receive_nothing(client, notifications, manager):
    with (
        connect(login(client), URL) as mine,
        connect(login(client, "other-session"), URL) as theirs,
    ):
        mine.receive_json()
        theirs.receive_json()
        notifications.add(USER_ID, match_notification(1))
        manager.notifications_changed([USER_ID])
        assert ids(mine.receive_json()) == [1]
        assert stays_silent(theirs)


def test_nothing_is_sent_without_a_notification(client):
    with connect(login(client), URL) as ws:
        ws.receive_json()
        assert stays_silent(ws)


def test_incoming_messages_are_ignored_and_do_not_close(client, manager):
    with connect(login(client), URL) as ws:
        ws.receive_json()
        ws.send_text("hola")
        ws.send_bytes(b"\x00\x01")
        ws.send_json({"type": "notifications"})
        assert stays_silent(ws)
        assert manager.count(USER_ID, USER_ID) == 1


def test_closing_releases_the_slot_and_the_subscription(client, manager):
    with connect(login(client), URL) as ws:
        ws.receive_json()
    assert wait_until(
        lambda: manager.subscribers(USER_ID) == [] and manager.count(USER_ID, USER_ID) == 0
    )


# --- fin de la sesión ---------------------------------------------------------


def test_log_out_closes_with_4401_session_ended(client, manager):
    with connect(login(client), URL) as ws:
        ws.receive_json()
        manager.session_ended("user-session")
        assert closing(ws) == (4401, "sessionEnded")


def test_log_out_keeps_the_connections_of_other_sessions(client, sessions, manager):
    sessions.add("second-session", USER_ID)
    with (
        connect(login(client), URL) as closed,
        connect(login(client, "second-session"), URL) as kept,
    ):
        closed.receive_json()
        kept.receive_json()
        manager.session_ended("user-session")
        assert closing(closed) == (4401, "sessionEnded")
        assert stays_silent(kept)


def test_session_expiry_closes_with_4401_session_ended(client, sessions):
    sessions.add("short", USER_ID, expires_at=datetime.now(timezone.utc) + timedelta(seconds=0.5))
    with connect(login(client, "short"), URL) as ws:
        ws.receive_json()
        assert closing(ws) == (4401, "sessionEnded")
