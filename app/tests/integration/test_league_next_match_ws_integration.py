"""/ws/leagues/{id}/matches/next contra la base real (Postgres)."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from itertools import combinations
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, update
from sqlalchemy.orm import sessionmaker

from app.api import ws_deps, ws_league_deps
from app.api.ws_league_deps import get_league_channel_managers, get_league_next_match_manager
from app.domain.match import MatchStatus
from app.main import app
from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.services.league_next_match_channel import LeagueNextMatchManager
from app.tests.league_ws_helpers import (
    ORIGIN,
    closing,
    connect,
    rejection,
    stays_silent,
    wait_until,
)

pytestmark = pytest.mark.integration

START = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


@pytest.fixture()
def manager():
    return LeagueNextMatchManager(ws_league_deps._load_fixture_state)


@pytest.fixture(autouse=True)
def wiring(client, db_session, monkeypatch, manager):
    """Cableado real; solo se redirige SessionLocal a la base de tests."""
    monkeypatch.setattr(
        ws_league_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)
    app.dependency_overrides[get_league_next_match_manager] = lambda: manager
    app.dependency_overrides[get_league_channel_managers] = lambda: [manager]
    yield
    app.dependency_overrides.pop(get_league_next_match_manager, None)
    app.dependency_overrides.pop(get_league_channel_managers, None)


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC")


@pytest.fixture()
def viewer(create_user):
    return create_user("viewer", "Viewer FC")


@pytest.fixture()
def started_league(db_session, creator, create_user, make_league, add_participant):
    """Liga en curso con 3 participantes y un partido por par.

    Devuelve (id, ids de partidos por fecha, usuarios). El primer partido es
    usuarios[0] contra usuarios[1].
    """

    def _make(name="Liga", private=False):
        league = make_league(creator, name=name, status="started", private=private)
        users = [creator]
        for i in range(2):
            user = create_user(f"{name.lower()}{i}")
            add_participant(league, user)
            users.append(user)
        matches = [
            Match(
                league_id=league.id,
                user_1_id=a.id,
                user_2_id=b.id,
                status=MatchStatus.scheduled,
                scheduled_at=START + timedelta(hours=i),
            )
            for i, (a, b) in enumerate(combinations(users, 2))
        ]
        db_session.add_all(reversed(matches))  # ids en orden inverso a las fechas
        db_session.commit()
        return league.id, [m.id for m in matches], users

    return _make


@pytest.fixture()
def runner_callback(db_session, monkeypatch, manager):
    """El callback real del runner, con la base de tests y el manager del test."""
    monkeypatch.setattr(
        ws_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    monkeypatch.setattr(ws_deps, "get_league_next_match_manager", lambda: manager)
    return ws_deps._notify_league_channels


def path(league_id: int) -> str:
    return f"/ws/leagues/{league_id}/matches/next"


def set_league_status(db_session, league_id, status):
    db_session.execute(update(League).where(League.id == league_id).values(status=status))
    db_session.commit()


def set_match(db_session, match_id, **values):
    db_session.execute(update(Match).where(Match.id == match_id).values(**values))
    db_session.commit()


# --- mensaje ------------------------------------------------------------------


def test_the_match_is_the_first_of_get_fixture_plus_playable(login_as, started_league, viewer):
    league_id, _, _ = started_league()
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        message = ws.receive_json()

    rest = api.get(f"/leagues/{league_id}/fixture")
    assert rest.status_code == 200
    assert (message["type"], message["leagueStatus"]) == ("leagueNextMatch", "started")
    assert message["match"] == {**rest.json()[0], "playable": False}


def test_playable_for_both_clubs_and_not_for_others(login_as, started_league, viewer):
    league_id, _, (club_1, club_2, outsider) = started_league()
    sockets = {}
    with ExitStack() as stack:
        for user in (club_1, club_2, outsider, viewer):
            sockets[user.id] = stack.enter_context(connect(login_as(user), path(league_id)))
        playable = {uid: ws.receive_json()["match"]["playable"] for uid, ws in sockets.items()}

    assert playable == {club_1.id: True, club_2.id: True, outsider.id: False, viewer.id: False}


def test_a_started_match_is_the_next_one(login_as, db_session, started_league, viewer):
    league_id, (_, second, _), _ = started_league()
    set_match(db_session, second, status=MatchStatus.started)

    with connect(login_as(viewer), path(league_id)) as ws:
        match = ws.receive_json()["match"]
    assert (match["id"], match["status"]) == (second, "started")


def test_same_date_is_broken_by_id(login_as, db_session, started_league, viewer):
    league_id, (first, second, _), _ = started_league()
    set_match(db_session, second, scheduled_at=START)  # empata con el primero

    with connect(login_as(viewer), path(league_id)) as ws:
        # Ids en orden inverso a las fechas: `second` tiene el id menor.
        assert ws.receive_json()["match"]["id"] == second


# --- handshake ----------------------------------------------------------------


def test_missing_origin_is_4403(client, started_league):
    league_id, _, _ = started_league()
    assert rejection(client, path(league_id), origin=None) == (4403, "originNotAllowed")


def test_no_cookie_is_4401(client, started_league):
    league_id, _, _ = started_league()
    assert rejection(client, path(league_id)) == (4401, "sessionInvalid")


def test_expired_session_is_4401(login_as, started_league, viewer):
    league_id, _, _ = started_league()
    api = login_as(viewer, expires_in=timedelta(days=-1))
    assert rejection(api, path(league_id)) == (4401, "sessionInvalid")


def test_unknown_league_is_4404(login_as, viewer):
    assert rejection(login_as(viewer), path(2147483647)) == (4404, "leagueNotFound")


@pytest.mark.parametrize(
    "status, reason",
    [
        ("preparation", "leagueNotStarted"),
        ("finished", "leagueFinished"),
        ("cancelled", "leagueCancelled"),
    ],
)
def test_league_not_started_is_4409(login_as, make_league, creator, status, reason):
    league = make_league(creator, status=status)
    assert rejection(login_as(creator), path(league.id)) == (4409, reason)


def test_private_league_requires_access(login_as, started_league, creator, viewer):
    league_id, _, _ = started_league(private=True)
    assert rejection(login_as(viewer), path(league_id)) == (4403, "leagueAccessRequired")
    with connect(login_as(creator), path(league_id)) as ws:
        assert ws.receive_json()["leagueStatus"] == "started"


def test_unlock_is_per_session(login_as, started_league, viewer):
    league_id, _, _ = started_league(private=True)
    api = login_as(viewer)
    assert api.post(f"/leagues/{league_id}/access", json={"password": "secret"}).status_code == 204

    with connect(api, path(league_id)) as ws:
        assert ws.receive_json()["type"] == "leagueNextMatch"
    assert rejection(login_as(viewer), path(league_id)) == (4403, "leagueAccessRequired")


def test_sixth_connection_is_4429(login_as, started_league, viewer, manager):
    league_id, _, _ = started_league()
    api = login_as(viewer)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(api, path(league_id)))
        assert rejection(api, path(league_id)) == (4429, "tooManyConnections")
        assert manager.count(league_id, viewer.id) == 5


def test_incoming_messages_are_ignored(login_as, started_league, viewer, manager):
    league_id, _, _ = started_league()
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()
        ws.send_text("hola")
        assert stays_silent(ws)
        assert manager.count(league_id, viewer.id) == 1


# --- avisos del runner --------------------------------------------------------


def test_only_league_matches_notify_their_league(
    db_session, started_league, creator, create_user, monkeypatch
):
    league_id, (first, _, _), _ = started_league()
    friendly = Match(user_1_id=creator.id, user_2_id=create_user("rival").id)
    db_session.add(friendly)
    db_session.commit()

    monkeypatch.setattr(ws_deps, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    calls = []
    monkeypatch.setattr(
        ws_deps,
        "get_league_next_match_manager",
        lambda: SimpleNamespace(next_match_changed=calls.append),
    )

    ws_deps._notify_league_channels(first)
    ws_deps._notify_league_channels(friendly.id)
    assert calls == [league_id]


def test_match_start_and_end_send_the_new_next_match(
    login_as, db_session, started_league, viewer, runner_callback
):
    league_id, (first, second, _), _ = started_league()
    repo = SqlAlchemyMatchRepository(db_session)
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()

        repo.mark_started(first)
        runner_callback(first)
        started = ws.receive_json()["match"]
        assert (started["id"], started["status"]) == (first, "started")

        assert repo.finish(first, 2, 0) is False
        runner_callback(first)
        message = ws.receive_json()
        assert message["leagueStatus"] == "started"
        assert (message["match"]["id"], message["match"]["status"]) == (second, "scheduled")


def test_messages_of_one_league_do_not_reach_another(
    login_as, db_session, started_league, viewer, runner_callback
):
    league_id, (first, _, _), _ = started_league("Una")
    other_id, _, _ = started_league("Otra")
    api = login_as(viewer)
    with connect(api, path(league_id)) as mine, connect(api, path(other_id)) as theirs:
        mine.receive_json()
        theirs.receive_json()
        SqlAlchemyMatchRepository(db_session).mark_started(first)
        runner_callback(first)
        assert mine.receive_json()["match"]["status"] == "started"
        assert stays_silent(theirs)


def test_the_last_match_sends_a_single_null_message_and_closes(
    login_as, db_session, started_league, viewer, runner_callback, manager
):
    league_id, (first, second, last), _ = started_league()
    repo = SqlAlchemyMatchRepository(db_session)
    repo.finish(first, 1, 0)
    repo.finish(second, 1, 0)
    api = login_as(viewer)

    with connect(api, path(league_id)) as ws:
        assert ws.receive_json()["match"]["id"] == last

        # El resultado y el fin de la liga se guardan juntos (SCRUM-162): un solo aviso.
        assert repo.finish(last, 0, 1) is True
        runner_callback(last)

        assert ws.receive_json() == {
            "type": "leagueNextMatch",
            "leagueStatus": "finished",
            "match": None,
        }
        assert closing(ws) == (1000, "leagueFinished")

    assert wait_until(lambda: manager.count(league_id, viewer.id) == 0)
    assert rejection(api, path(league_id)) == (4409, "leagueFinished")


def test_cancelled_league_sends_a_null_message_and_closes(
    login_as, db_session, started_league, viewer, manager
):
    league_id, _, _ = started_league()
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()
        set_league_status(db_session, league_id, LeagueStatus.cancelled)
        manager.next_match_changed(league_id)
        assert ws.receive_json() == {
            "type": "leagueNextMatch",
            "leagueStatus": "cancelled",
            "match": None,
        }
        assert closing(ws) == (1000, "leagueCancelled")


def test_leaving_the_league_keeps_the_connection(
    login_as, db_session, started_league, runner_callback, manager
):
    league_id, (first, _, _), (_, club_2, _) = started_league()
    with connect(login_as(club_2), path(league_id)) as ws:
        ws.receive_json()
        db_session.execute(
            delete(LeagueParticipant).where(
                LeagueParticipant.league_id == league_id,
                LeagueParticipant.user_id == club_2.id,
            )
        )
        db_session.commit()

        SqlAlchemyMatchRepository(db_session).mark_started(first)
        runner_callback(first)
        assert ws.receive_json()["match"]["status"] == "started"
        assert manager.count(league_id, club_2.id) == 1


# --- log-out ------------------------------------------------------------------


def test_log_out_closes_its_connections_with_4401(login_as, started_league, viewer):
    league_id, _, _ = started_league()
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        ws.receive_json()
        assert api.post("/auth/log-out").status_code == 204
        assert closing(ws) == (4401, "sessionEnded")


def test_log_out_keeps_the_connections_of_other_sessions(login_as, started_league, viewer):
    league_id, _, _ = started_league()
    mine, other = login_as(viewer), login_as(viewer)

    with connect(mine, path(league_id)) as closed, connect(other, path(league_id)) as kept:
        closed.receive_json()
        kept.receive_json()

        assert mine.post("/auth/log-out").status_code == 204

        assert closing(closed) == (4401, "sessionEnded")
        assert stays_silent(kept)
