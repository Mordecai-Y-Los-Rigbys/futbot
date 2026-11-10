"""/ws/leagues/{id}/ranking contra la base real (Postgres)."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from itertools import combinations
from types import SimpleNamespace

import pytest
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.api import ws_deps, ws_league_deps
from app.api.ws_league_deps import (
    get_league_channel_managers,
    get_league_participants_manager,
    get_league_ranking_manager,
)
from app.domain.match import MatchStatus
from app.main import app
from app.models.league import League, LeagueStatus
from app.models.match import Match
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.services.league_fixture_channel import LeagueFixtureManager
from app.services.league_participants_manager import LeagueParticipantsManager
from app.services.league_ranking_channel import LeagueRankingManager
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
    return LeagueRankingManager(ws_league_deps._load_ranking_state)


@pytest.fixture()
def channels(manager):
    """El log-out cierra las conexiones en los managers de participantes y ranking del test."""
    participants = LeagueParticipantsManager(ws_league_deps._load_participants_state)
    app.dependency_overrides[get_league_participants_manager] = lambda: participants
    app.dependency_overrides[get_league_channel_managers] = lambda: [participants, manager]
    yield participants
    app.dependency_overrides.pop(get_league_participants_manager, None)
    app.dependency_overrides.pop(get_league_channel_managers, None)


@pytest.fixture(autouse=True)
def wiring(client, db_session, monkeypatch, manager):
    """Cableado real; solo se redirige SessionLocal a la base de tests."""
    monkeypatch.setattr(
        ws_league_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)
    app.dependency_overrides[get_league_ranking_manager] = lambda: manager
    yield
    app.dependency_overrides.pop(get_league_ranking_manager, None)


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
        db_session.add_all(matches)
        db_session.commit()
        return league.id, [m.id for m in matches]

    return _make


@pytest.fixture()
def runner_callbacks(db_session, monkeypatch, manager):
    """Los callbacks reales del runner, con la base de tests. El fixture va a un manager aparte."""
    monkeypatch.setattr(
        ws_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    monkeypatch.setattr(ws_deps, "get_league_ranking_manager", lambda: manager)
    monkeypatch.setattr(
        ws_deps,
        "get_league_fixture_manager",
        lambda: LeagueFixtureManager(ws_league_deps._load_fixture_state),
    )
    return ws_deps._notify_league_channels, ws_deps._notify_league_ranking


def path(league_id: int) -> str:
    return f"/ws/leagues/{league_id}/ranking"


def set_league_status(db_session, league_id, status):
    db_session.execute(update(League).where(League.id == league_id).values(status=status))
    db_session.commit()


def by_name(message) -> dict[str, dict]:
    return {e["name"]: e for e in message["ranking"]}


# --- mensaje ------------------------------------------------------------------


def test_the_message_matches_get_ranking(login_as, db_session, started_league, viewer):
    league_id, (first, _, _) = started_league()
    SqlAlchemyMatchRepository(db_session).finish(first, 2, 1)
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        message = ws.receive_json()

    rest = api.get(f"/leagues/{league_id}/ranking")
    assert rest.status_code == 200
    assert (message["type"], message["leagueStatus"]) == ("leagueRanking", "started")
    assert message["ranking"] == rest.json()


def test_just_started_league_has_one_entry_per_participant_at_zero(
    login_as, started_league, viewer
):
    league_id, _ = started_league()
    with connect(login_as(viewer), path(league_id)) as ws:
        ranking = ws.receive_json()["ranking"]

    assert len(ranking) == 3
    for e in ranking:
        assert e["position"] == 1
        assert (e["played"], e["score"], e["goals"], e["goalDifference"]) == (0, 0, 0, 0)


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
        assert ws.receive_json()["type"] == "leagueRanking"
    assert rejection(login_as(viewer), path(league_id)) == (4403, "leagueAccessRequired")


def test_sixth_connection_is_4429(login_as, started_league, viewer, manager):
    league_id, _ = started_league()
    api = login_as(viewer)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(api, path(league_id)))
        assert rejection(api, path(league_id)) == (4429, "tooManyConnections")
        assert manager.count(league_id, viewer.id) == 5


# --- avisos del runner --------------------------------------------------------


def test_the_runner_notifies_the_ranking_only_when_a_match_finishes():
    runner = ws_deps.get_match_runner()
    assert runner._on_match_finished is ws_deps._notify_league_ranking


def test_only_league_matches_notify_their_league(
    db_session, started_league, creator, create_user, monkeypatch
):
    league_id, (first, _, _) = started_league()
    friendly = Match(user_1_id=creator.id, user_2_id=create_user("rival").id)
    db_session.add(friendly)
    db_session.commit()

    monkeypatch.setattr(ws_deps, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    calls = []
    monkeypatch.setattr(
        ws_deps, "get_league_ranking_manager", lambda: SimpleNamespace(ranking_changed=calls.append)
    )

    ws_deps._notify_league_ranking(first)
    ws_deps._notify_league_ranking(friendly.id)
    assert calls == [league_id]


def test_a_match_start_sends_nothing_and_its_result_sends_the_ranking(
    login_as, db_session, started_league, viewer, runner_callbacks
):
    on_change, on_finished = runner_callbacks
    league_id, (first, _, _) = started_league()
    repo = SqlAlchemyMatchRepository(db_session)
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()

        # El runner solo llama a on_match_change al empezar el partido.
        repo.mark_started(first)
        on_change(first)

        assert repo.finish(first, 2, 0) is False
        on_change(first)
        on_finished(first)

        # Si el inicio hubiera emitido algo, este primer mensaje vendría en cero.
        message = ws.receive_json()
        assert message["leagueStatus"] == "started"
        assert [e["score"] for e in message["ranking"]] == [3, 0, 0]
        assert message["ranking"][0]["played"] == 1
        assert stays_silent(ws)


def test_messages_of_one_league_do_not_reach_another(
    login_as, db_session, started_league, viewer, runner_callbacks
):
    _, on_finished = runner_callbacks
    league_id, (first, _, _) = started_league("Una")
    other_id, _ = started_league("Otra")
    api = login_as(viewer)
    with connect(api, path(league_id)) as mine, connect(api, path(other_id)) as theirs:
        mine.receive_json()
        theirs.receive_json()
        SqlAlchemyMatchRepository(db_session).finish(first, 1, 0)
        on_finished(first)
        assert mine.receive_json()["ranking"][0]["score"] == 3
        assert stays_silent(theirs)


def test_the_last_match_sends_a_single_message_and_closes(
    login_as, db_session, started_league, viewer, runner_callbacks, manager
):
    _, on_finished = runner_callbacks
    league_id, (first, second, last) = started_league()
    repo = SqlAlchemyMatchRepository(db_session)
    repo.finish(first, 1, 0)
    repo.finish(second, 1, 0)

    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        ws.receive_json()

        # El resultado y el fin de la liga se guardan juntos (SCRUM-162): un solo aviso.
        assert repo.finish(last, 0, 1) is True
        on_finished(last)

        message = ws.receive_json()
        assert message["leagueStatus"] == "finished"
        assert all(e["played"] == 2 for e in message["ranking"])
        assert closing(ws) == (1000, "leagueFinished")

    assert wait_until(lambda: manager.count(league_id, viewer.id) == 0)
    assert message["ranking"] == api.get(f"/leagues/{league_id}/ranking").json()
    assert rejection(api, path(league_id)) == (4409, "leagueFinished")


def test_cancelled_league_sends_an_empty_ranking_and_closes(
    login_as, db_session, started_league, viewer, manager
):
    league_id, _ = started_league()
    with connect(login_as(viewer), path(league_id)) as ws:
        ws.receive_json()
        set_league_status(db_session, league_id, LeagueStatus.cancelled)
        manager.ranking_changed(league_id)
        message = ws.receive_json()
        assert (message["leagueStatus"], message["ranking"]) == ("cancelled", [])
        assert closing(ws) == (1000, "leagueCancelled")


# --- log-out ------------------------------------------------------------------


def test_log_out_closes_the_session_connections(login_as, started_league, viewer, channels):
    league_id, _ = started_league()
    api = login_as(viewer)
    with connect(api, path(league_id)) as ws:
        ws.receive_json()
        assert api.post("/auth/log-out").status_code == 204
        assert closing(ws) == (4401, "sessionEnded")


def test_log_out_keeps_the_connections_of_other_sessions(
    login_as, started_league, viewer, channels
):
    league_id, _ = started_league()
    mine, other = login_as(viewer), login_as(viewer)

    with connect(mine, path(league_id)) as closed, connect(other, path(league_id)) as kept:
        closed.receive_json()
        kept.receive_json()

        assert mine.post("/auth/log-out").status_code == 204

        assert closing(closed) == (4401, "sessionEnded")
        assert stays_silent(kept)
