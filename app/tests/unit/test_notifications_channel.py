from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.errors import ApiError
from app.repositories.match_abstract import PenaltyShootoutData
from app.repositories.notification_abstract import NotificationsState
from app.services.notifications_channel import (
    NotificationsHandshakeService,
    NotificationsManager,
    build_notifications_payload,
)
from app.tests.unit.league_participants_fakes import ORIGIN, FakeSessions
from app.tests.unit.notification_fakes import (
    FakeNotifications,
    league_notification,
    match_notification,
)


def payload(*notifications, has_unseen=True):
    return build_notifications_payload(
        NotificationsState(has_unseen=has_unseen, notifications=list(notifications))
    )


# --- mensaje ------------------------------------------------------------------


def test_match_notification_matches_the_contract():
    assert payload(match_notification(3)) == {
        "type": "notifications",
        "new": True,
        "notifications": [
            {
                "id": 3,
                "kind": "matchFinished",
                "leagueId": 1,
                "leagueMatchId": 50,
                "seen": False,
                "createdAt": "2026-11-09T20:00:00Z",
                "club1": {"id": 7, "username": "user7", "name": "club7", "avatar": 2},
                "club2": {"id": 8, "username": "user8", "name": "club8", "avatar": 4},
                "result": {"score1": 2, "score2": 1, "penalties": None},
            }
        ],
    }


def test_league_notification_matches_the_contract():
    assert payload(league_notification(4, seen=True), has_unseen=False) == {
        "type": "notifications",
        "new": False,
        "notifications": [
            {
                "id": 4,
                "kind": "leagueFinished",
                "leagueId": 1,
                "leagueMatchId": None,
                "seen": True,
                "createdAt": "2026-11-09T20:00:00Z",
                "leagueName": "Liga",
            }
        ],
    }


@pytest.mark.parametrize("winner, club", [(1, "club1"), (2, "club2")])
def test_result_with_shootout_has_the_penalties(winner, club):
    kicks = [{"club": "club1", "kickerId": 3, "kickerName": "J3", "round": 1, "scored": True}]
    shootout = PenaltyShootoutData(score_1=4, score_2=3, winner=winner, kicks=kicks)
    result = payload(match_notification(1, penalties=shootout))["notifications"][0]["result"]
    assert result["penalties"] == {"score1": 4, "score2": 3, "winner": club, "kicks": kicks}


def test_naive_created_at_is_utc():
    naive = replace(match_notification(1), created_at=datetime(2026, 1, 2, 3, 4, 5))
    assert payload(naive)["notifications"][0]["createdAt"] == "2026-01-02T03:04:05Z"


def test_without_notifications_the_list_is_empty():
    assert payload(has_unseen=False) == {"type": "notifications", "new": False, "notifications": []}


def test_the_order_of_the_state_is_kept():
    message = payload(league_notification(9), match_notification(8))
    assert [n["id"] for n in message["notifications"]] == [9, 8]


# --- handshake ----------------------------------------------------------------


@pytest.fixture()
def handshake():
    sessions = FakeSessions()
    sessions.add("s1", 7)
    return NotificationsHandshakeService([ORIGIN], sessions)


def test_valid_handshake_returns_the_user_and_the_session(handshake):
    grant = handshake.authorize(ORIGIN, "s1")
    assert (grant.user_id, grant.session_id) == (7, "s1")
    assert grant.session_expires_at > datetime.now(timezone.utc)


@pytest.mark.parametrize("origin", [None, "", "http://evil.com"])
def test_origin_not_allowed_is_403(handshake, origin):
    with pytest.raises(ApiError) as exc:
        handshake.authorize(origin, "s1")
    assert (exc.value.status_code, exc.value.code) == (403, "originNotAllowed")


@pytest.mark.parametrize("session_id", [None, "", "no-existe", "x" * 65])
def test_session_invalid_is_401(handshake, session_id):
    with pytest.raises(ApiError) as exc:
        handshake.authorize(ORIGIN, session_id)
    assert (exc.value.status_code, exc.value.code) == (401, "sessionInvalid")


def test_origin_is_checked_before_the_session(handshake):
    with pytest.raises(ApiError) as exc:
        handshake.authorize(None, None)
    assert exc.value.code == "originNotAllowed"


# --- manager ------------------------------------------------------------------


class Spy:
    def __init__(self):
        self.notified = 0

    def notify(self):
        self.notified += 1


def test_notifications_changed_notifies_each_user_once():
    manager = NotificationsManager(FakeNotifications().get_state)
    spies = {}
    for user_id in (1, 2, 3):
        spies[user_id] = Spy()
        manager._subscribers[user_id] = {spies[user_id]}

    manager.notifications_changed([1, 2, 1, 2])

    assert {uid: s.notified for uid, s in spies.items()} == {1: 1, 2: 1, 3: 0}


def test_notifications_changed_without_connections_does_nothing():
    manager = NotificationsManager(FakeNotifications().get_state)
    manager.notifications_changed([1, 2])
    assert manager.subscribers(1) == []


def test_sixth_reservation_of_the_same_user_is_429():
    manager = NotificationsManager(FakeNotifications().get_state)
    for _ in range(5):
        manager.reserve(7, 7)
    with pytest.raises(ApiError) as exc:
        manager.reserve(7, 7)
    assert (exc.value.status_code, exc.value.code) == (429, "tooManyConnections")
    manager.reserve(8, 8)  # el límite es por usuario
