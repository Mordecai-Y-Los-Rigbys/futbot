from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.ws_league_deps import get_league_next_match_manager, get_next_match_handshake_scope
from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.main import app
from app.services.league_next_match_channel import (
    LeagueNextMatchHandshakeService,
    LeagueNextMatchManager,
)
from app.tests.league_ws_helpers import closing, connect, rejection, stays_silent, wait_until
from app.tests.unit.league_fixture_fakes import FakeFixtures, match
from app.tests.unit.league_participants_fakes import CREATOR_ID, ORIGIN, FakeLeagues, FakeSessions

USER_ID = 8  # no juega ningún partido de la liga 1
RIVAL_ID = 9


@pytest.fixture()
def sessions():
    repo = FakeSessions()
    repo.add("creator-session", CREATOR_ID)
    repo.add("user-session", USER_ID)
    repo.add("rival-session", RIVAL_ID)
    return repo


@pytest.fixture()
def leagues():
    repo = FakeLeagues()
    repo.add(1, status=LeagueStatus.started)
    repo.add(2, private=True, status=LeagueStatus.started)
    repo.add(3, status=LeagueStatus.started)
    return repo


@pytest.fixture()
def fixtures(leagues):
    repo = FakeFixtures(leagues)
    repo.set(1, [match(11, CREATOR_ID, 9, 0), match(12, CREATOR_ID, 10, 1), match(13, 9, 10, 2)])
    repo.set(2, [match(21, CREATOR_ID, 9)])
    repo.set(3, [match(31, CREATOR_ID, 9)])
    return repo


@pytest.fixture()
def manager(fixtures):
    return LeagueNextMatchManager(fixtures.get_state)


@pytest.fixture()
def client(sessions, leagues, manager):
    service = LeagueNextMatchHandshakeService([ORIGIN], sessions, leagues, leagues)

    @contextmanager
    def scope():
        yield service

    app.dependency_overrides[get_next_match_handshake_scope] = lambda: scope
    app.dependency_overrides[get_league_next_match_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def url(league_id=1):
    return f"/ws/leagues/{league_id}/matches/next"


def login(client, session="user-session"):
    client.cookies.clear()
    if session is not None:
        client.cookies.set("session_id", session)
    return client


# --- un test por cada cierre del handshake ------------------------------------


@pytest.mark.parametrize("origin", [None, "http://evil.com"])
def test_origin_not_allowed_is_4403(client, origin):
    assert rejection(login(client), url(), origin=origin) == (4403, "originNotAllowed")


@pytest.mark.parametrize("session", [None, "no-existe"])
def test_session_invalid_is_4401(client, session):
    assert rejection(login(client, session), url()) == (4401, "sessionInvalid")


@pytest.mark.parametrize("league_id", ["999", "0", "abc", "1.5", "2147483648"])
def test_league_not_found_or_invalid_id_is_4404(client, league_id):
    assert rejection(login(client), url(league_id)) == (4404, "leagueNotFound")


def test_private_league_without_access_is_4403_league_access_required(client):
    assert rejection(login(client), url(2)) == (4403, "leagueAccessRequired")


@pytest.mark.parametrize(
    "status, reason",
    [
        (LeagueStatus.preparation, "leagueNotStarted"),
        (LeagueStatus.finished, "leagueFinished"),
        (LeagueStatus.cancelled, "leagueCancelled"),
    ],
)
def test_league_not_started_is_4409_without_messages(client, leagues, status, reason):
    leagues.set_status(1, status)
    assert rejection(login(client), url()) == (4409, reason)


def test_sixth_connection_is_4429_and_the_others_keep_receiving(client, fixtures, manager):
    api = login(client)
    with ExitStack() as stack:
        sockets = [stack.enter_context(connect(api, url())) for _ in range(5)]
        for ws in sockets:
            ws.receive_json()

        assert rejection(api, url()) == (4429, "tooManyConnections")

        fixtures.update(1, 11, status=MatchStatus.started)
        manager.next_match_changed(1)
        for ws in sockets:
            assert ws.receive_json()["match"]["status"] == "started"


# --- orden de precedencia -----------------------------------------------------


def test_precedence_origin_beats_everything(client):
    assert rejection(login(client, None), url("abc"), origin=None) == (4403, "originNotAllowed")


def test_precedence_session_beats_league(client):
    assert rejection(login(client, "no-existe"), url("999")) == (4401, "sessionInvalid")


def test_precedence_league_beats_access(client):
    assert rejection(login(client), url("999")) == (4404, "leagueNotFound")


def test_precedence_access_beats_state(client, leagues):
    leagues.set_status(2, LeagueStatus.finished)
    assert rejection(login(client), url(2)) == (4403, "leagueAccessRequired")


def test_precedence_state_beats_connection_limit(client, leagues, manager):
    for _ in range(5):
        manager.reserve(1, USER_ID)
    leagues.set_status(1, LeagueStatus.preparation)
    assert rejection(login(client), url()) == (4409, "leagueNotStarted")


def test_rejected_handshake_leaves_no_registration(client, manager):
    rejection(login(client, "no-existe"), url())
    assert manager.subscribers(1) == [] and manager._reserved == {}


# --- conexión aceptada --------------------------------------------------------


def test_the_next_match_arrives_on_connect(client):
    with connect(login(client), url()) as ws:
        message = ws.receive_json()
    assert (message["type"], message["leagueStatus"]) == ("leagueNextMatch", "started")
    assert (message["match"]["id"], message["match"]["status"]) == (11, "scheduled")
    assert message["match"]["playable"] is False


def test_a_started_match_is_the_next_one(client, fixtures):
    fixtures.update(1, 12, status=MatchStatus.started)
    with connect(login(client), url()) as ws:
        assert ws.receive_json()["match"]["id"] == 12


def test_playable_is_true_for_both_clubs_and_false_for_others_at_once(client):
    # La cookie se lee al abrir cada conexión
    with (
        connect(login(client, "creator-session"), url()) as creator,
        connect(login(client, "rival-session"), url()) as rival,
        connect(login(client), url()) as viewer,
    ):
        assert creator.receive_json()["match"]["playable"] is True
        assert rival.receive_json()["match"]["playable"] is True
        assert viewer.receive_json()["match"]["playable"] is False


@pytest.mark.parametrize("who", ["creator", "participant", "unlocked"])
def test_private_league_opens_for_creator_participant_or_unlocked_session(client, leagues, who):
    session = "creator-session" if who == "creator" else "user-session"
    if who == "participant":
        leagues.join(2, USER_ID)
    if who == "unlocked":
        leagues.unlock("user-session", 2)
    with connect(login(client, session), url(2)) as ws:
        assert ws.receive_json()["leagueStatus"] == "started"


def test_unlocking_in_another_session_gives_no_access(client, sessions, leagues):
    sessions.add("other-session", USER_ID)
    leagues.unlock("other-session", 2)
    assert rejection(login(client), url(2)) == (4403, "leagueAccessRequired")


def test_incoming_messages_are_ignored_and_do_not_close(client, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        ws.send_text("hola")
        ws.send_bytes(b"\x00\x01")
        ws.send_json({"type": "leagueNextMatch"})
        assert stays_silent(ws)
        assert manager.count(1, USER_ID) == 1


def test_closing_releases_the_slot_and_the_subscription(client, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
    assert wait_until(lambda: manager.subscribers(1) == [] and manager.count(1, USER_ID) == 0)


# --- cambios mientras la conexión está abierta --------------------------------


def test_match_started_and_finished_send_the_new_next_match(client, fixtures, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()

        fixtures.update(1, 11, status=MatchStatus.started)
        manager.next_match_changed(1)
        started = ws.receive_json()["match"]
        assert (started["id"], started["status"]) == (11, "started")

        fixtures.update(1, 11, status=MatchStatus.finished, score_1=2, score_2=1)
        manager.next_match_changed(1)
        message = ws.receive_json()
        assert message["leagueStatus"] == "started"
        assert (message["match"]["id"], message["match"]["status"]) == (12, "scheduled")


def test_messages_of_one_league_do_not_reach_another(client, fixtures, manager):
    api = login(client)
    with connect(api, url(1)) as mine, connect(api, url(3)) as other:
        mine.receive_json()
        other.receive_json()
        fixtures.update(1, 11, status=MatchStatus.started)
        manager.next_match_changed(1)
        assert mine.receive_json()["match"]["status"] == "started"
        assert stays_silent(other)


def test_last_match_sends_a_single_null_message_and_closes_1000(client, leagues, fixtures, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        for match_id in (11, 12, 13):
            fixtures.update(1, match_id, status=MatchStatus.finished, score_1=1, score_2=0)
        leagues.set_status(1, LeagueStatus.finished)
        manager.next_match_changed(1)

        assert ws.receive_json() == {
            "type": "leagueNextMatch",
            "leagueStatus": "finished",
            "match": None,
        }
        assert closing(ws) == (1000, "leagueFinished")

    assert wait_until(lambda: manager.count(1, USER_ID) == 0)
    assert rejection(login(client), url()) == (4409, "leagueFinished")


def test_cancelled_league_sends_a_null_message_and_closes_1000(client, leagues, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        leagues.set_status(1, LeagueStatus.cancelled)
        manager.next_match_changed(1)
        assert ws.receive_json() == {
            "type": "leagueNextMatch",
            "leagueStatus": "cancelled",
            "match": None,
        }
        assert closing(ws) == (1000, "leagueCancelled")


def test_log_out_closes_with_4401_session_ended(client, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        manager.session_ended("user-session")
        assert closing(ws) == (4401, "sessionEnded")


def test_session_expiry_closes_with_4401_session_ended(client, sessions):
    sessions.add("short", USER_ID, expires_at=datetime.now(timezone.utc) + timedelta(seconds=0.5))
    with connect(login(client, "short"), url()) as ws:
        ws.receive_json()
        assert closing(ws) == (4401, "sessionEnded")


def test_leaving_the_league_does_not_close_the_connection(client, leagues, fixtures, manager):
    leagues.join(1, USER_ID)
    with connect(login(client), url()) as ws:
        ws.receive_json()
        leagues.leave(1, USER_ID)
        fixtures.update(1, 11, status=MatchStatus.started)
        manager.next_match_changed(1)
        assert ws.receive_json()["match"]["status"] == "started"
        assert manager.count(1, USER_ID) == 1
