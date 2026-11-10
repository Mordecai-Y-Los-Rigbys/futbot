from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.ws_league_deps import get_league_ranking_manager, get_ranking_handshake_scope
from app.domain.league import LeagueStatus
from app.main import app
from app.services.league_ranking_channel import LeagueRankingHandshakeService, LeagueRankingManager
from app.tests.league_ws_helpers import closing, connect, rejection, stays_silent, wait_until
from app.tests.unit.league_participants_fakes import CREATOR_ID, ORIGIN, FakeLeagues, FakeSessions
from app.tests.unit.league_ranking_fakes import FakeRankings
from app.tests.unit.repo_fakes import ranking_club as club

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
    repo.add(1, status=LeagueStatus.started)
    repo.add(2, private=True, status=LeagueStatus.started)
    repo.add(3, status=LeagueStatus.started)
    return repo


@pytest.fixture()
def rankings(leagues):
    repo = FakeRankings(leagues)
    repo.set(1, [club(CREATOR_ID), club(9), club(10)])
    repo.set(2, [club(CREATOR_ID), club(9)])
    repo.set(3, [club(CREATOR_ID), club(9)])
    return repo


@pytest.fixture()
def manager(rankings):
    return LeagueRankingManager(rankings.get_state)


@pytest.fixture()
def client(sessions, leagues, manager):
    service = LeagueRankingHandshakeService([ORIGIN], sessions, leagues, leagues)

    @contextmanager
    def scope():
        yield service

    app.dependency_overrides[get_ranking_handshake_scope] = lambda: scope
    app.dependency_overrides[get_league_ranking_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def url(league_id=1):
    return f"/ws/leagues/{league_id}/ranking"


def login(client, session="user-session"):
    client.cookies.clear()
    if session is not None:
        client.cookies.set("session_id", session)
    return client


def names(message) -> list[str]:
    return [e["name"] for e in message["ranking"]]


def finish_match(rankings, league_id, winner, loser):
    """Lo que deja en la base un 1 a 0 de `winner` sobre `loser`."""
    rankings.update(league_id, winner, won_regular=1, goals_for=1)
    rankings.update(league_id, loser, lost=1, goals_against=1)


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


def test_sixth_connection_is_4429_and_the_others_keep_receiving(client, rankings, manager):
    api = login(client)
    with ExitStack() as stack:
        sockets = [stack.enter_context(connect(api, url())) for _ in range(5)]
        for ws in sockets:
            ws.receive_json()

        assert rejection(api, url()) == (4429, "tooManyConnections")

        finish_match(rankings, 1, 10, CREATOR_ID)
        manager.ranking_changed(1)
        for ws in sockets:
            assert names(ws.receive_json())[0] == "Club 10"


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


def test_the_full_ranking_arrives_on_connect(client):
    with connect(login(client), url()) as ws:
        message = ws.receive_json()
    assert (message["type"], message["leagueStatus"]) == ("leagueRanking", "started")
    assert names(message) == [f"Club {CREATOR_ID}", "Club 9", "Club 10"]
    assert all(e["position"] == 1 and e["score"] == 0 for e in message["ranking"])


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
        ws.send_json({"type": "leagueRanking"})
        assert stays_silent(ws)
        assert manager.count(1, USER_ID) == 1


def test_closing_releases_the_slot_and_the_subscription(client, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
    assert wait_until(lambda: manager.subscribers(1) == [] and manager.count(1, USER_ID) == 0)


# --- cambios mientras la conexión está abierta --------------------------------


def test_a_finished_match_sends_the_full_ranking(client, rankings, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()

        finish_match(rankings, 1, 9, 10)
        manager.ranking_changed(1)

        message = ws.receive_json()
        assert message["leagueStatus"] == "started"
        assert names(message) == ["Club 9", f"Club {CREATOR_ID}", "Club 10"]
        assert [e["position"] for e in message["ranking"]] == [1, 2, 3]
        assert [e["score"] for e in message["ranking"]] == [3, 0, 0]


def test_nothing_is_sent_without_a_notification(client):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        assert stays_silent(ws)


def test_messages_of_one_league_do_not_reach_another(client, rankings, manager):
    api = login(client)
    with connect(api, url(1)) as mine, connect(api, url(3)) as other:
        mine.receive_json()
        other.receive_json()
        finish_match(rankings, 1, 9, 10)
        manager.ranking_changed(1)
        assert names(mine.receive_json())[0] == "Club 9"
        assert stays_silent(other)


def test_last_match_sends_a_single_message_and_closes_1000(client, leagues, rankings, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        finish_match(rankings, 1, 9, 10)
        leagues.set_status(1, LeagueStatus.finished)
        manager.ranking_changed(1)

        message = ws.receive_json()
        assert message["leagueStatus"] == "finished"
        assert names(message)[0] == "Club 9"
        assert closing(ws) == (1000, "leagueFinished")

    assert wait_until(lambda: manager.count(1, USER_ID) == 0)
    assert rejection(login(client), url()) == (4409, "leagueFinished")


def test_cancelled_league_sends_an_empty_ranking_and_closes_1000(client, leagues, manager):
    with connect(login(client), url()) as ws:
        ws.receive_json()
        leagues.set_status(1, LeagueStatus.cancelled)
        manager.ranking_changed(1)
        assert ws.receive_json() == {
            "type": "leagueRanking",
            "leagueStatus": "cancelled",
            "ranking": [],
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


def test_leaving_the_league_does_not_close_the_connection(client, leagues, rankings, manager):
    leagues.join(1, USER_ID)
    with connect(login(client), url()) as ws:
        ws.receive_json()
        leagues.leave(1, USER_ID)
        finish_match(rankings, 1, 9, 10)
        manager.ranking_changed(1)
        assert names(ws.receive_json())[0] == "Club 9"
        assert manager.count(1, USER_ID) == 1
