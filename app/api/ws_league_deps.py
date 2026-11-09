from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.config import allowed_origins
from app.database import SessionLocal
from app.repositories.league_access_sqlalchemy import SqlAlchemyLeagueAccessRepository
from app.repositories.league_participants_abstract import LeagueParticipantsState
from app.repositories.league_participants_sqlalchemy import SqlAlchemyLeagueParticipantsRepository
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository
from app.repositories.ranking_sqlalchemy import SqlAlchemyRankingRepository
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.services.league_channel_manager import LeagueChannelManager
from app.services.league_fixture_channel import (
    LeagueFixtureHandshakeService,
    LeagueFixtureManager,
    LeagueFixtureState,
)
from app.services.league_fixture_notifier import LeagueFixtureNotifier
from app.services.league_participants_handshake import LeagueParticipantsHandshakeService
from app.services.league_participants_manager import LeagueParticipantsManager
from app.services.league_participants_notifier import LeagueParticipantsNotifier
from app.services.league_ranking_channel import (
    LeagueRankingHandshakeService,
    LeagueRankingManager,
    LeagueRankingState,
)
from app.services.session_service import SessionService


def _load_participants_state(league_id: int) -> LeagueParticipantsState | None:
    with SessionLocal() as db:
        return SqlAlchemyLeagueParticipantsRepository(db).get_state(league_id)


_participants_manager = LeagueParticipantsManager(_load_participants_state)


def get_league_participants_manager() -> LeagueParticipantsManager:
    return _participants_manager


def get_league_participants_notifier() -> LeagueParticipantsNotifier:
    return _participants_manager


@contextmanager
def _participants_handshake_scope() -> Iterator[LeagueParticipantsHandshakeService]:
    with SessionLocal() as db:
        yield LeagueParticipantsHandshakeService(
            allowed_origins(),
            SessionService(SqlAlchemySessionRepository(db)),
            SqlAlchemyLeagueAccessRepository(db),
            SqlAlchemyLeagueParticipantsRepository(db),
        )


def get_participants_handshake_scope() -> (
    Callable[[], ContextManager[LeagueParticipantsHandshakeService]]
):
    return _participants_handshake_scope


def _load_fixture_state(league_id: int) -> LeagueFixtureState | None:
    with SessionLocal() as db:
        data = SqlAlchemyLeagueRepository(db).get_fixture(league_id)
    if data is None:
        return None
    return LeagueFixtureState(league_id=league_id, status=data.status, matches=data.matches)


_fixture_manager = LeagueFixtureManager(_load_fixture_state)


def get_league_fixture_manager() -> LeagueFixtureManager:
    return _fixture_manager


def get_league_fixture_notifier() -> LeagueFixtureNotifier:
    return _fixture_manager


@contextmanager
def _fixture_handshake_scope() -> Iterator[LeagueFixtureHandshakeService]:
    with SessionLocal() as db:
        yield LeagueFixtureHandshakeService(
            allowed_origins(),
            SessionService(SqlAlchemySessionRepository(db)),
            SqlAlchemyLeagueAccessRepository(db),
            SqlAlchemyLeagueParticipantsRepository(db),  # solo se usa get_status
        )


def get_fixture_handshake_scope() -> (
    Callable[[], ContextManager[LeagueFixtureHandshakeService]]
):
    return _fixture_handshake_scope


def _load_ranking_state(league_id: int) -> LeagueRankingState | None:
    with SessionLocal() as db:
        repo = SqlAlchemyRankingRepository(db)
        status = repo.get_league_status(league_id)
        if status is None:
            return None
        return LeagueRankingState(status=status, clubs=repo.list_league_club_totals(league_id))


_ranking_manager = LeagueRankingManager(_load_ranking_state)


def get_league_ranking_manager() -> LeagueRankingManager:
    return _ranking_manager


@contextmanager
def _ranking_handshake_scope() -> Iterator[LeagueRankingHandshakeService]:
    with SessionLocal() as db:
        yield LeagueRankingHandshakeService(
            allowed_origins(),
            SessionService(SqlAlchemySessionRepository(db)),
            SqlAlchemyLeagueAccessRepository(db),
            SqlAlchemyLeagueParticipantsRepository(db),  # solo se usa get_status
        )


def get_ranking_handshake_scope() -> (
    Callable[[], ContextManager[LeagueRankingHandshakeService]]
):
    return _ranking_handshake_scope


def get_league_channel_managers() -> list[LeagueChannelManager]:
    """Managers de todos los canales de liga. El log-out cierra en cada uno las conexiones de la sesión."""
    return [_participants_manager, _fixture_manager, _ranking_manager]
