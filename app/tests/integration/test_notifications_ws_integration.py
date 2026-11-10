"""/ws/notifications contra la base real (Postgres), con el cableado real."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.api import ws_deps, ws_league_deps, ws_notification_deps
from app.domain.match import MatchStatus
from app.models.league import League, LeagueStatus
from app.models.match import Match
from app.models.notification import Notification
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.tests.league_ws_helpers import (
    ORIGIN,
    closing,
    connect,
    rejection,
    stays_silent,
    wait_until,
)

pytestmark = pytest.mark.integration

URL = "/ws/notifications"
START = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


@pytest.fixture()
def manager():
    return ws_notification_deps.get_notifications_manager()


@pytest.fixture(autouse=True)
def wiring(client, db_session, monkeypatch):
    """Cableado real; solo se redirige SessionLocal a la base de tests."""
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind())
    for module in (ws_notification_deps, ws_league_deps, ws_deps):
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC", avatar=2)


@pytest.fixture()
def outsider(create_user):
    return create_user("outsider", "Outsider FC")


@pytest.fixture()
def league(db_session, creator, create_user, make_league, add_participant):
    """Liga en curso con 3 participantes y 2 partidos. Devuelve (liga, usuarios, partidos)."""
    lg = make_league(creator, name="Copa", status="started")
    a, b = create_user("a", "A FC", avatar=3), create_user("b", "B FC", avatar=4)
    for user in (a, b):
        add_participant(lg, user)
    matches = [
        Match(
            league_id=lg.id,
            user_1_id=x.id,
            user_2_id=y.id,
            status=MatchStatus.started,
            scheduled_at=START + timedelta(hours=i),
        )
        for i, (x, y) in enumerate([(creator, a), (a, b)])
    ]
    db_session.add_all(matches)
    db_session.commit()
    return lg, [creator, a, b], matches


def finish_and_notify(db_session, match_id, score_1=1, score_2=0) -> bool:
    """Lo que hace el runner al terminar un partido."""
    finished = SqlAlchemyMatchRepository(db_session).finish(match_id, score_1, score_2)
    ws_deps._notify_match_finished(match_id)
    return finished


def count_notifications(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(Notification))


# --- handshake ----------------------------------------------------------------


def test_missing_origin_is_4403(login_as, creator):
    assert rejection(login_as(creator), URL, origin=None) == (4403, "originNotAllowed")


def test_origin_is_checked_before_the_session(client):
    assert rejection(client, URL, origin="http://evil.com") == (4403, "originNotAllowed")


def test_no_cookie_is_4401(client):
    assert rejection(client, URL) == (4401, "sessionInvalid")


def test_expired_session_is_4401(login_as, creator):
    api = login_as(creator, expires_in=timedelta(days=-1))
    assert rejection(api, URL) == (4401, "sessionInvalid")


def test_sixth_connection_is_4429(login_as, creator, manager):
    api = login_as(creator)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(api, URL)).receive_json()
        assert rejection(api, URL) == (4429, "tooManyConnections")
        assert manager.count(creator.id, creator.id) == 5
    assert wait_until(lambda: manager.count(creator.id, creator.id) == 0)


# --- mensajes -----------------------------------------------------------------


def test_on_connect_the_user_gets_the_current_state(login_as, db_session, league):
    lg, (creator, a, b), (first, _) = league
    SqlAlchemyMatchRepository(db_session).finish(first.id, 2, 1)

    with connect(login_as(b), URL) as ws:
        message = ws.receive_json()

    assert (message["type"], message["new"]) == ("notifications", True)
    [n] = message["notifications"]
    assert n["kind"] == "matchFinished"
    assert (n["leagueId"], n["leagueMatchId"], n["seen"]) == (lg.id, first.id, False)
    assert n["createdAt"].endswith("Z")
    assert n["club1"] == {
        "id": creator.id,
        "username": "creator",
        "name": "Creator FC",
        "avatar": 2,
    }
    assert n["club2"] == {"id": a.id, "username": "a", "name": "A FC", "avatar": 3}
    assert n["result"] == {"score1": 2, "score2": 1, "penalties": None}


def test_participants_with_the_channel_open_receive_it_and_others_do_not(
    login_as, db_session, league, outsider
):
    _, (creator, a, b), (first, _) = league
    with connect(login_as(b), URL) as participant, connect(login_as(outsider), URL) as other:
        assert participant.receive_json()["notifications"] == []
        assert other.receive_json()["notifications"] == []

        assert finish_and_notify(db_session, first.id) is False

        message = participant.receive_json()
        assert message["new"] is True
        assert [n["leagueMatchId"] for n in message["notifications"]] == [first.id]
        assert stays_silent(other)


def test_the_last_match_sends_one_message_with_the_league_first(login_as, db_session, league):
    _, (creator, _, _), (first, last) = league
    SqlAlchemyMatchRepository(db_session).finish(first.id, 1, 0)

    with connect(login_as(creator), URL) as ws:
        ws.receive_json()
        assert finish_and_notify(db_session, last.id, 0, 3) is True

        message = ws.receive_json()
        notifications = message["notifications"]
        assert [n["kind"] for n in notifications] == [
            "leagueFinished",
            "matchFinished",
            "matchFinished",
        ]
        assert notifications[0] == {
            "id": notifications[0]["id"],
            "kind": "leagueFinished",
            "leagueId": notifications[0]["leagueId"],
            "leagueMatchId": None,
            "seen": False,
            "createdAt": notifications[0]["createdAt"],
            "leagueName": "Copa",
        }
        assert notifications[1]["leagueMatchId"] == last.id
        assert stays_silent(ws)


def test_a_failed_close_creates_nothing_and_sends_nothing(
    login_as, db_session, league, monkeypatch
):
    _, (creator, _, _), (first, last) = league
    SqlAlchemyMatchRepository(db_session).finish(first.id, 1, 0)
    before = count_notifications(db_session)

    original = SqlAlchemyMatchRepository._add_notifications

    def failing(self, league_id, league_match_id):
        original(self, league_id, league_match_id)
        if league_match_id is None:
            raise RuntimeError("falla al cerrar la liga")

    monkeypatch.setattr(SqlAlchemyMatchRepository, "_add_notifications", failing)
    with connect(login_as(creator), URL) as ws:
        ws.receive_json()
        with pytest.raises(RuntimeError):
            SqlAlchemyMatchRepository(db_session).finish(last.id, 1, 0)
        assert stays_silent(ws)

    db_session.expire_all()
    assert count_notifications(db_session) == before
    assert db_session.get(Match, last.id).status == MatchStatus.started
    assert db_session.get(League, last.league_id).status == LeagueStatus.started


def test_a_friendly_sends_nothing(login_as, db_session, creator, outsider):
    friendly = Match(user_1_id=creator.id, user_2_id=outsider.id, status=MatchStatus.started)
    db_session.add(friendly)
    db_session.commit()
    with connect(login_as(creator), URL) as ws:
        ws.receive_json()
        finish_and_notify(db_session, friendly.id)
        assert stays_silent(ws)
    assert count_notifications(db_session) == 0


def test_client_messages_are_ignored(login_as, creator, manager):
    with connect(login_as(creator), URL) as ws:
        ws.receive_json()
        ws.send_text("hola")
        assert stays_silent(ws)
        assert manager.count(creator.id, creator.id) == 1


def test_the_runner_notifies_the_notifications_when_a_match_finishes(monkeypatch):
    calls = []
    monkeypatch.setattr(ws_deps, "_notify_league_ranking", lambda match_id: None)
    monkeypatch.setattr(ws_deps, "_notify_notifications", calls.append)
    ws_deps.get_match_runner()._on_match_finished(5)
    assert calls == [5]


# --- log-out ------------------------------------------------------------------


def test_log_out_closes_the_session_connections(login_as, creator):
    api = login_as(creator)
    with connect(api, URL) as ws:
        ws.receive_json()
        assert api.post("/auth/log-out").status_code == 204
        assert closing(ws) == (4401, "sessionEnded")


def test_log_out_keeps_the_connections_of_other_sessions(login_as, creator):
    mine, other = login_as(creator), login_as(creator)
    with connect(mine, URL) as closed, connect(other, URL) as kept:
        closed.receive_json()
        kept.receive_json()
        assert mine.post("/auth/log-out").status_code == 204
        assert closing(closed) == (4401, "sessionEnded")
        assert stays_silent(kept)
