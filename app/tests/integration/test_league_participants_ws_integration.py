"""/ws/leagues/{id}/participants contra la base real (Postgres)."""

import threading
import time
from contextlib import ExitStack
from datetime import timedelta

import pytest
from anyio import EndOfStream
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.api import ws_league_deps
from app.api.ws_league_deps import (
    get_league_participants_manager,
    get_league_participants_notifier,
)
from app.domain.behavior import BehaviorType
from app.main import app
from app.models.behavior import Behavior
from app.models.league import League, LeagueStatus
from app.models.player import Player
from app.services.league_participants_manager import LeagueParticipantsManager

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


@pytest.fixture()
def manager():
    return LeagueParticipantsManager(ws_league_deps._load_participants_state)


@pytest.fixture(autouse=True)
def wiring(client, db_session, monkeypatch, manager):
    """Cableado real; solo se redirige SessionLocal a la base de tests."""
    monkeypatch.setattr(
        ws_league_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)
    app.dependency_overrides[get_league_participants_manager] = lambda: manager
    app.dependency_overrides[get_league_participants_notifier] = lambda: manager
    yield
    app.dependency_overrides.pop(get_league_participants_manager, None)
    app.dependency_overrides.pop(get_league_participants_notifier, None)


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC")


@pytest.fixture()
def joiner(create_user):
    return create_user("joiner", "Joiner FC")


@pytest.fixture()
def viewer(create_user):
    return create_user("viewer", "Viewer FC")


@pytest.fixture()
def team_body(db_session):
    """team_body(user) -> body válido para POST /leagues/{id}/participants."""

    def _make(user):
        players = [
            Player(
                user_id=user.id,
                name=f"J{i}",
                power=60,
                agility=60,
                control=60,
                strength=60,
                speed=60,
            )
            for i in range(6)
        ]
        behaviors = [
            Behavior(
                user_id=user.id,
                name=f"b{user.id}_{i}",
                code="def behave(): pass",
                type=BehaviorType.player_behavior,
            )
            for i in range(6)
        ]
        db_session.add_all(players + behaviors)
        db_session.commit()
        members = [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ]
        return {"members": members}

    return _make


def path(league_id: int) -> str:
    return f"/ws/leagues/{league_id}/participants"


def connect(api, league, origin=ORIGIN):
    """`league` es una League o directamente un id."""
    league_id = league if isinstance(league, int) else league.id
    headers = {} if origin is None else {"Origin": origin}
    return api.websocket_connect(path(league_id), headers=headers)


def rejection(api, league, origin=ORIGIN) -> tuple[int, str]:
    with pytest.raises(WebSocketDisconnect) as exc:
        with connect(api, league, origin) as ws:
            message = ws.receive_text()
            pytest.fail(f"el rechazo no debería enviar mensajes: {message}")
    return exc.value.code, exc.value.reason


def stays_silent(ws, seconds=0.5) -> bool:
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


def usernames(message) -> list[str]:
    return [p["username"] for p in message["participants"]]


def set_status(db_session, league_id, status):
    db_session.execute(update(League).where(League.id == league_id).values(status=status))
    db_session.commit()


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# --- handshake ----------------------------------------------------------------


def test_public_league_opens_for_any_user_with_the_current_list(
    login_as, make_league, creator, viewer
):
    league = make_league(creator)
    with connect(login_as(viewer), league) as ws:
        assert ws.receive_json() == {
            "type": "leagueParticipants",
            "leagueStatus": "preparation",
            "participants": [
                {"id": creator.id, "username": "creator", "name": "Creator FC", "avatar": 1}
            ],
        }


def test_missing_origin_is_4403_before_the_session(client, make_league, creator):
    league = make_league(creator)
    assert rejection(client, league, origin=None) == (4403, "originNotAllowed")


def test_no_cookie_is_4401(client, make_league, creator):
    league = make_league(creator)
    assert rejection(client, league) == (4401, "sessionInvalid")


def test_expired_session_is_4401(login_as, make_league, creator, viewer):
    league = make_league(creator)
    api = login_as(viewer, expires_in=timedelta(days=-1))
    assert rejection(api, league) == (4401, "sessionInvalid")


def test_unknown_league_is_4404(login_as, viewer):
    assert rejection(login_as(viewer), 2147483647) == (4404, "leagueNotFound")


def test_private_league_requires_access(login_as, make_league, creator, viewer, add_participant):
    league = make_league(creator, private=True)
    assert rejection(login_as(viewer), league) == (4403, "leagueAccessRequired")

    with connect(login_as(creator), league) as ws:
        assert ws.receive_json()["leagueStatus"] == "preparation"

    add_participant(league, viewer)
    with connect(login_as(viewer), league) as ws:
        assert usernames(ws.receive_json()) == ["creator", "viewer"]


def test_private_league_opens_for_a_session_that_unlocked_it(
    login_as, make_league, creator, viewer
):
    league = make_league(creator, private=True)
    api = login_as(viewer)
    assert api.post(f"/leagues/{league.id}/access", json={"password": "secret"}).status_code == 204
    with connect(api, league) as ws:
        assert ws.receive_json()["type"] == "leagueParticipants"


def test_started_league_is_4409_without_messages(login_as, make_league, creator):
    league = make_league(creator, status="started")
    assert rejection(login_as(creator), league) == (4409, "leagueNotInPreparation")


def test_sixth_connection_is_4429(login_as, make_league, creator, viewer, manager):
    league = make_league(creator)
    api = login_as(viewer)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(connect(api, league))
        assert rejection(api, league) == (4429, "tooManyConnections")
        assert manager.count(league.id, viewer.id) == 5


# --- unirse y abandonar por REST ----------------------------------------------


def test_join_and_leave_through_the_api_reach_the_open_connection(
    login_as, make_league, creator, joiner, viewer, team_body
):
    league = make_league(creator)
    body = team_body(joiner)
    joiner_api = login_as(joiner)

    with connect(login_as(viewer), league) as ws:
        assert usernames(ws.receive_json()) == ["creator"]

        assert joiner_api.post(f"/leagues/{league.id}/participants", json=body).status_code == 201
        message = ws.receive_json()
        assert message["leagueStatus"] == "preparation"
        assert usernames(message) == ["creator", "joiner"]

        assert joiner_api.delete(f"/leagues/{league.id}/participants/me").status_code == 204
        assert usernames(ws.receive_json()) == ["creator"]


def test_a_failed_join_sends_nothing(login_as, make_league, creator, joiner, viewer, team_body):
    league = make_league(creator, max_participants=1)  # llena: solo el creador
    body = team_body(joiner)

    with connect(login_as(viewer), league) as ws:
        ws.receive_json()
        resp = login_as(joiner).post(f"/leagues/{league.id}/participants", json=body)
        assert resp.status_code == 409 and resp.json()["code"] == "leagueFull"
        assert stays_silent(ws)


def test_leaving_does_not_close_the_leavers_connection(
    login_as, make_league, creator, joiner, add_participant
):
    league = make_league(creator)
    add_participant(league, joiner)
    api = login_as(joiner)

    with connect(api, league) as ws:
        assert usernames(ws.receive_json()) == ["creator", "joiner"]
        assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204
        assert usernames(ws.receive_json()) == ["creator"]
        assert stays_silent(ws)


def test_messages_of_one_league_do_not_reach_another(
    login_as, make_league, creator, joiner, viewer, team_body
):
    league, other = make_league(creator, "Una"), make_league(creator, "Otra")
    body = team_body(joiner)
    api = login_as(viewer)

    with connect(api, league) as mine, connect(api, other) as theirs:
        mine.receive_json()
        theirs.receive_json()
        assert (
            login_as(joiner).post(f"/leagues/{league.id}/participants", json=body).status_code
            == 201
        )
        assert usernames(mine.receive_json()) == ["creator", "joiner"]
        assert stays_silent(theirs)


# --- fin de la preparación y de la sesión -------------------------------------


@pytest.mark.parametrize(
    "status, reason",
    [(LeagueStatus.started, "leagueStarted"), (LeagueStatus.cancelled, "leagueCancelled")],
)
def test_start_or_cancel_sends_the_last_message_and_closes(
    login_as, db_session, make_league, creator, viewer, manager, status, reason
):
    league = make_league(creator)
    league_id = league.id
    api = login_as(viewer)

    with connect(api, league) as ws:
        ws.receive_json()
        # Lo que harán los endpoints de iniciar y cancelar
        set_status(db_session, league_id, status)
        manager.league_status_changed(league_id)

        assert ws.receive_json()["leagueStatus"] == status.value
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert (exc.value.code, exc.value.reason) == (1000, reason)

    assert wait_until(lambda: manager.count(league_id, viewer.id) == 0)
    assert rejection(api, league) == (4409, "leagueNotInPreparation")


def test_session_end_closes_its_connections_with_4401(
    login_as, make_league, creator, viewer, manager
):
    league = make_league(creator)
    api = login_as(viewer)
    with connect(api, league) as ws:
        ws.receive_json()
        manager.session_ended(api.cookies.get("session_id"))
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert (exc.value.code, exc.value.reason) == (4401, "sessionEnded")
