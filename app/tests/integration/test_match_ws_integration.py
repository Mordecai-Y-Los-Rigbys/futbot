from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from starlette.testclient import WebSocketDenialResponse

from app.api import ws_deps
from app.api.ws_deps import get_connection_manager
from app.main import app
from app.models.match import Match, MatchStatus
from app.models.match_ws_token import MatchWsToken
from app.services.match_connection_manager import MatchConnectionManager

pytestmark = pytest.mark.integration


@pytest.fixture()
def manager():
    return MatchConnectionManager()


@pytest.fixture()
def client(db_session, monkeypatch, manager):
    """Usa el cableado real (ws_deps._handshake_service_scope con repos
    SQLAlchemy); solo se redirige SessionLocal a la base de tests."""
    monkeypatch.setattr(
        ws_deps,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind()),
    )
    app.dependency_overrides[get_connection_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def make_match(db_session, make_user):
    """Partido amistoso. Respeta los CHECK del modelo: un partido que arrancó
    o terminó necesita rival, y uno terminado necesita resultado."""

    def _make(status=MatchStatus.scheduled) -> Match:
        home = make_user(900)
        away = make_user(901) if status != MatchStatus.scheduled else None
        match = Match(
            home_user_id=home.id,
            away_user_id=away.id if away else None,
            status=status,
            home_score=1 if status == MatchStatus.finished else None,
            away_score=0 if status == MatchStatus.finished else None,
        )
        db_session.add(match)
        db_session.commit()
        return match

    return _make


@pytest.fixture()
def make_token(db_session, make_user):
    def _make(token, user_id, match, expires_in=timedelta(hours=2)) -> str:
        make_user(user_id)
        now = datetime.now(timezone.utc)
        db_session.add(
            MatchWsToken(
                token=token,
                user_id=user_id,
                match_id=match.id,
                created_at=now - timedelta(days=1),
                expires_at=now + expires_in,
            )
        )
        db_session.commit()
        return token

    return _make


def path(match, token):
    return f"/ws/matches/{match.id}?token={token}"


def denied(client, p) -> WebSocketDenialResponse:
    with pytest.raises(WebSocketDenialResponse) as exc:
        with client.websocket_connect(p):
            pass
    return exc.value


def test_valid_token_opens_the_connection(client, make_match, make_token, manager):
    match = make_match()
    make_token("tok", 7, match)
    with client.websocket_connect(path(match, "tok")):
        assert manager.count(match.id, 7) == 1
    assert manager.count(match.id, 7) == 0


def test_same_token_reconnects(client, make_match, make_token):
    match = make_match()
    make_token("tok", 7, match)
    for _ in range(2):
        with client.websocket_connect(path(match, "tok")):
            pass


def test_unknown_token_is_401(client, make_match):
    match = make_match()
    resp = denied(client, path(match, "no-existe"))
    assert resp.status_code == 401
    assert resp.json()["code"] is None


def test_missing_token_is_401(client, make_match):
    match = make_match()
    assert denied(client, f"/ws/matches/{match.id}").status_code == 401


def test_expired_token_is_401(client, make_match, make_token):
    match = make_match()
    make_token("viejo", 7, match, expires_in=timedelta(seconds=-1))
    assert denied(client, path(match, "viejo")).status_code == 401


def test_token_of_another_match_is_403(client, make_match, make_token):
    mine, other = make_match(), make_match()
    make_token("tok", 7, mine)
    resp = denied(client, path(other, "tok"))
    assert resp.status_code == 403
    assert resp.json()["code"] is None


def test_finished_match_is_409_even_with_a_valid_token(client, make_match, make_token):
    match = make_match(status=MatchStatus.finished)
    make_token("tok", 7, match)
    resp = denied(client, path(match, "tok"))
    assert resp.status_code == 409
    assert resp.json()["code"] == "matchFinished"


def test_sixth_connection_of_the_same_user_is_429(client, make_match, make_token):
    from contextlib import ExitStack

    match = make_match()
    make_token("tok", 7, match)
    with ExitStack() as stack:
        for _ in range(5):
            stack.enter_context(client.websocket_connect(path(match, "tok")))
        assert denied(client, path(match, "tok")).status_code == 429


@pytest.mark.parametrize("status", [MatchStatus.scheduled, MatchStatus.started])
def test_connecting_and_disconnecting_does_not_change_the_match(
    client, db_session, make_match, make_token, status
):
    match = make_match(status=status)
    make_token("tok", 7, match)

    with client.websocket_connect(path(match, "tok")):
        pass

    db_session.refresh(match)
    assert match.status == status