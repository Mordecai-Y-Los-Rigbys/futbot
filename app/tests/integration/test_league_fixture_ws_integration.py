"""/ws/leagues/{id}/fixture contra la base real (Postgres)."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from itertools import combinations
from types import SimpleNamespace

import pytest
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.api import ws_league_deps
from app.api.ws_league_deps import get_league_fixture_manager, get_league_fixture_notifier
from app.domain.match import MatchStatus
from app.main import app
from app.models.league import League, LeagueStatus
from app.models.match import Match
from app.services.league_fixture_channel import LeagueFixtureManager
from app.tests.league_ws_helpers import ORIGIN, closing, connect, rejection, stays_silent, wait_until

pytestmark = pytest.mark.integration

START = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


@pytest.fixture()
def manager():
    return LeagueFixtureManager(ws_league_deps._load_fixture_state)


@pytest.fixture(autouse=True)
def wiring(client, db_session, monkeypatch, manager):
    """Cableado real; solo se redirige SessionLocal a la base de tests."""
    monkeypatch.setattr(
        ws_league_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)
    app.dependency_overrides[get_league_fixture_manager] = lambda: manager
    app.dependency_overrides[get_league_fixture_notifier] = lambda: manager
    yield
    app.dependency_overrides.pop(get_league_fixture_manager, None)
    app.dependency_overrides.pop(get_league_fixture_notifier, None)


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC")


@pytest.fixture()
def viewer(create_user):
    return create_user("viewer", "Viewer FC")


@pytest.fixture()
def started_league(db_session, creator, create_user, make_league, add_participant):
    """Liga en curso con 3 participantes y un partido por par. Devuelve (id, ids de partidos)."""

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
        return league.id, [m.id for m in matches]

    return _make


def path(league_id: int) -> str:
    return f"/ws/leagues/{league_id}/fixture"


def set_league_status(db_session, league_id, status):
    db_session.execute(update(League).where(League.id == league_id).values(status=status))
    db_session.commit()


def set_match(db_session, match_id, **values):
    db_session.execute(update(Match).where(Match.id == match_id).values(**values))
    db_session.commit()


def by_id(message) -> dict[int, dict]:
    return {m["id"]: m for m in message["fixture"]}


# --- mensaje ------------------------------------------------------------------


def test_the_message_matches_get_fixture(login_as, started_league, viewer):
    league_id, _ = started_league()
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        message = ws.receive_json()

    rest = api.get(f"/leagues/{league_id}/fixture")
    assert rest.status_code == 200
    assert (message["type"], message["leagueStatus"]) == ("leagueFixture", "started")
    assert message["fixture"] == rest.json()


def test_ordered_by_scheduled_at_and_then_by_id(login_as, db_session, started_league, viewer):
    league_id, (first, second, third) = started_league()
    set_match(db_session, second, scheduled_at=START)  # empata con el primero

    with connect(login_as(viewer), path(league_id)) as ws:
        message = ws.receive_json()

    # Ids en orden inverso a las fechas: el desempate pone a `second` antes que `first`.
    assert [m["id"] for m in message["fixture"]] == [second, first, third]


# --- handshake ----------------------------------------------------------------


def test_missing_origin_is_4403(client, started_league):
    league_id, _ = started_league()
    assert rejection(client, path(league_id), origin=None) == (4403, "originNotAllowed")


def test_no_cookie_is_4401(client, started_league):
    league_id, _ = started_league()
    assert rejection(client, path(league_id)) == (4401, "sessionInvalid")


def test_expired_session_is_4401(login_as, started_league, viewer):
    league_id, _ = started_league()
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
    league_id, _ = started_league(private=True)
    assert rejection(login_as(viewer), path(league_id)) == (4403, "leagueAccessRequired")
    with connect(login_as(creator), path(league_id)) as ws:
        assert ws.receive_json()["leagueStatus"] == "started"


def test_unlock_is_per_session(login_as, started_league, viewer):
    league_id, _ = started_league(private=True)
    api = login_as(viewer)
    assert api.post(f"/leagues/{league_id}/access", json={"password": "secret"}).status_code == 204

    with connect(api, path(league_id)) as ws:
        assert ws.receive_json()["type"] == "leagueFixture"
    assert rejection(login_as(viewer), path(league_id)) == (4403, "leagueAccessRequired")


def test_sixth_connection_is_4429(login_as, started_league, viewer, manager):
    league_id, _ = started_league()
    api = login_as(viewer)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(api, path(league_id)))
        assert rejection(api, path(league_id)) == (4429, "tooManyConnections")
        assert manager.count(league_id, viewer.id) == 5


# --- cambios ------------------------------------------------------------------


def test_match_started_and_finished_reach_the_open_connection(
    login_as, db_session, started_league, viewer, manager
):
    league_id, (first, _, _) = started_league()
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()

        set_match(db_session, first, status=MatchStatus.started)
        manager.fixture_changed(league_id)
        assert by_id(ws.receive_json())[first]["status"] == "started"

        set_match(db_session, first, status=MatchStatus.finished, score_1=3, score_2=1)
        manager.fixture_changed(league_id)
        finished = by_id(ws.receive_json())[first]
        assert finished["status"] == "finished"
        assert finished["result"] == {"score1": 3, "score2": 1, "penalties": None}


def test_messages_of_one_league_do_not_reach_another(
    login_as, db_session, started_league, viewer, manager
):
    league_id, (first, _, _) = started_league("Una")
    other_id, _ = started_league("Otra")
    api = login_as(viewer)
    with connect(api, path(league_id)) as mine, connect(api, path(other_id)) as theirs:
        mine.receive_json()
        theirs.receive_json()
        set_match(db_session, first, status=MatchStatus.started)
        manager.fixture_changed(league_id)
        assert by_id(mine.receive_json())[first]["status"] == "started"
        assert stays_silent(theirs)


def test_finished_league_sends_the_last_message_and_closes(
    login_as, db_session, started_league, viewer, manager
):
    league_id, match_ids = started_league()
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        ws.receive_json()
        for match_id in match_ids:
            set_match(db_session, match_id, status=MatchStatus.finished, score_1=1, score_2=0)
        set_league_status(db_session, league_id, LeagueStatus.finished)
        manager.fixture_changed(league_id)

        message = ws.receive_json()
        assert message["leagueStatus"] == "finished"
        assert all(m["status"] == "finished" for m in message["fixture"])
        assert closing(ws) == (1000, "leagueFinished")

    assert wait_until(lambda: manager.count(league_id, viewer.id) == 0)
    assert rejection(api, path(league_id)) == (4409, "leagueFinished")


def test_cancelled_league_sends_an_empty_fixture_and_closes(
    login_as, db_session, started_league, viewer, manager
):
    league_id, _ = started_league()
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()
        set_league_status(db_session, league_id, LeagueStatus.cancelled)
        manager.fixture_changed(league_id)
        message = ws.receive_json()
        assert (message["leagueStatus"], message["fixture"]) == ("cancelled", [])
        assert closing(ws) == (1000, "leagueCancelled")


def test_log_out_closes_its_connections_with_4401(login_as, started_league, viewer, manager):
    league_id, _ = started_league()
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        ws.receive_json()
        manager.session_ended(api.cookies.get("session_id"))
        assert closing(ws) == (4401, "sessionEnded")


# --- inicio de la liga --------------------------------------------------------


def test_starting_the_league_notifies_the_fixture_channel(
    login_as, make_league, creator, create_user, add_participant
):
    league = make_league(creator)
    for name in ("p2", "p3"):
        add_participant(league, create_user(name))
    calls = []
    app.dependency_overrides[get_league_fixture_notifier] = lambda: SimpleNamespace(
        fixture_changed=calls.append
    )

    assert login_as(creator).post(f"/leagues/{league.id}/start").status_code == 204
    assert calls == [league.id]