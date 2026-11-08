import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.domain.match import MatchStatus
from app.main import app
from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.user import User
from app.repositories.session_abstract import CreateSessionData
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.tests.integration.match_factories import add_league, add_team


@pytest.fixture()
def create_user(db_session):
    def _create(username: str, club_name: str | None = None) -> User:
        user = User(
            username=username,
            email=f"{username}@test.com",
            password_hash="x",
            club_name=club_name or f"club-{username}",
            avatar=1,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _create


def _new_league(creator, name, status, max_participants, private):
    return League(
        name=name,
        creator_id=creator.id,
        status=LeagueStatus(status),
        min_participants=3,
        max_participants=max_participants,
        match_duration=5,
        private=private,
        password="secret" if private else None,
    )


@pytest.fixture()
def make_league(db_session):
    """Crea una liga e inscribe al creador como participante (como hace la app)."""

    def _make(
        creator, name="Liga", status="preparation", max_participants=8, private=False
    ) -> League:
        league = _new_league(creator, name, status, max_participants, private)
        db_session.add(league)
        db_session.flush()
        db_session.add(LeagueParticipant(league_id=league.id, user_id=creator.id))
        db_session.commit()
        return league

    return _make


@pytest.fixture()
def make_leagues_bulk(db_session):
    """Muchas ligas del mismo creador en un solo commit. Devuelve los ids."""

    def _make(creator, names: list[str], status="preparation") -> list[int]:
        leagues = [_new_league(creator, n, status, 8, False) for n in names]
        db_session.add_all(leagues)
        db_session.flush()
        db_session.add_all(LeagueParticipant(league_id=lg.id, user_id=creator.id) for lg in leagues)
        db_session.commit()
        return [lg.id for lg in leagues]

    return _make


@pytest.fixture()
def add_participant(db_session):
    def _add(league, user):
        db_session.add(LeagueParticipant(league_id=league.id, user_id=user.id))
        db_session.commit()

    return _add


@pytest.fixture()
def session_repo(db_session):
    return SqlAlchemySessionRepository(db_session)


@pytest.fixture()
def login_as(client, session_repo):
    """Crea una sesión real en la tabla de sesiones y devuelve un cliente con la
    cookie `session_id`. No se hace override de la auth. `client` se pide solo
    para que el override de get_db esté activo."""

    def _login(user, expires_in: timedelta = timedelta(days=1)) -> TestClient:
        # Márgenes de días (no de minutos): si la columna es naive, una
        # diferencia de huso horario no cambia el resultado.
        now = datetime.now(timezone.utc)
        token = uuid.uuid4().hex
        session_repo.create(
            CreateSessionData(
                id=token,
                user_id=user.id,
                created_at=min(now, now + expires_in) - timedelta(days=1),
                expires_at=now + expires_in,
            )
        )
        api = TestClient(app)
        api.cookies.set("session_id", token)
        return api

    return _login


@pytest.fixture()
def count_queries(db_session):
    """Uso: `with count_queries() as statements: ...; len(statements)`."""
    engine = db_session.get_bind()

    @contextmanager
    def _count():
        statements = []

        def _on(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _on)
        try:
            yield statements
        finally:
            event.remove(engine, "before_cursor_execute", _on)

    return _count


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    from app.services import friendly_expiry

    monkeypatch.setattr(friendly_expiry, "EXPIRY_RETRY_DELAY", 0)


@pytest.fixture()
def league_match(db_session, make_user, make_behaviors):
    """Partido de liga `started` entre 1 y 2, con sus equipos de liga."""
    make_user(1), make_user(2)
    league = add_league(db_session)
    teams = {}
    for uid in (1, 2):
        db_session.add(LeagueParticipant(league_id=league.id, user_id=uid))
        db_session.flush()
        behavior = make_behaviors(uid, ["b"], code="pass")[0]
        teams[uid] = add_team(db_session, uid, behavior, league_id=league.id)
    match = Match(
        league_id=league.id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(match)
    db_session.commit()
    return match, teams


@pytest.fixture()
def friendly_match(db_session, make_user, make_behaviors):
    """Amistoso `started` entre 1 y 2, con sus equipos del amistoso."""
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2, status=MatchStatus.started)
    db_session.add(match)
    db_session.commit()
    teams = {
        uid: add_team(
            db_session, uid, make_behaviors(uid, ["fb"], code="pass")[0], match_id=match.id
        )
        for uid in (1, 2)
    }
    return match, teams
