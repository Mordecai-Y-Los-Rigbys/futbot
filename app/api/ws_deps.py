from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.api.ws_league_deps import get_league_fixture_manager, get_league_next_match_manager
from app.database import SessionLocal
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository
from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository
from app.repositories.league_match_start_sqlalchemy import SqlAlchemyLeagueMatchStartRepository
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.match_start_sqlalchemy import SqlAlchemyMatchStartRepository
from app.repositories.match_ws_token_sqlalchemy import SqlAlchemyMatchWsTokenRepository
from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository
from app.services.friendly_expiry import FriendlyExpiryService
from app.services.friendly_start import FriendlyStartService
from app.services.league_match_start import LeagueMatchStartService
from app.services.match_connection_manager import MatchConnectionManager
from app.services.match_handshake_service import MatchHandshakeService
from app.services.match_runner import MatchRunner
from app.services.match_setup_service import MatchSetup, MatchSetupService

# Único registro de conexiones del proceso.
_connection_manager = MatchConnectionManager()


def get_connection_manager() -> MatchConnectionManager:
    return _connection_manager


@contextmanager
def _handshake_service_scope() -> Iterator[MatchHandshakeService]:
    """Sesión de DB de vida corta: solo para validar el handshake.

    No se usa Depends(get_db) a propósito: en un WebSocket esa dependencia
    seguiría abierta hasta que se cierre la conexión (todo el partido), y cada
    espectador retendría una conexión del pool de la base.
    """
    with SessionLocal() as db:
        yield MatchHandshakeService(
            SqlAlchemyMatchWsTokenRepository(db),
            SqlAlchemyMatchRepository(db),
        )


def get_handshake_service_scope() -> Callable[[], ContextManager[MatchHandshakeService]]:
    return _handshake_service_scope


@contextmanager
def _expiry_repo_scope() -> Iterator[SqlAlchemyMatchExpiryRepository]:
    with SessionLocal() as db:
        yield SqlAlchemyMatchExpiryRepository(db)


_friendly_expiry = FriendlyExpiryService(_expiry_repo_scope, _connection_manager.close_match)


def get_friendly_expiry() -> FriendlyExpiryService:
    return _friendly_expiry


@contextmanager
def _start_repo_scope() -> Iterator[SqlAlchemyMatchStartRepository]:
    with SessionLocal() as db:
        yield SqlAlchemyMatchStartRepository(db)


@contextmanager
def _match_repo_scope() -> Iterator[SqlAlchemyMatchRepository]:
    with SessionLocal() as db:
        yield SqlAlchemyMatchRepository(db)


def _load_setup(match_id: int) -> MatchSetup:
    with SessionLocal() as db:
        return MatchSetupService(
            SqlAlchemyMatchRepository(db),
            SqlAlchemyLeagueRepository(db),
            SqlAlchemyTeamRepository(db),
        ).load_match_setup(match_id)


@contextmanager
def _substitution_repo_scope() -> Iterator[SqlAlchemySubstitutionRepository]:
    with SessionLocal() as db:
        yield SqlAlchemySubstitutionRepository(db)
        

def _notify_league_channels(match_id: int) -> None:
    """Avisa a los canales de la liga del partido. Un amistoso no tiene liga: no hace nada."""
    with SessionLocal() as db:
        data = SqlAlchemyMatchRepository(db).get_setup_data(match_id)
    if data is not None and data.league_id is not None:
        get_league_fixture_manager().fixture_changed(data.league_id)
        get_league_next_match_manager().next_match_changed(data.league_id)


_match_runner = MatchRunner(
    _connection_manager,
    _load_setup,
    _match_repo_scope,
    _substitution_repo_scope,
    on_match_change=_notify_league_channels,
)


async def _start_simulation(match_id: int) -> None:
    _match_runner.start(match_id)  # start() es sync y devuelve la Task


_friendly_start = FriendlyStartService(_start_repo_scope, _start_simulation)


@contextmanager
def _league_match_start_repo_scope() -> Iterator[SqlAlchemyLeagueMatchStartRepository]:
    with SessionLocal() as db:
        yield SqlAlchemyLeagueMatchStartRepository(db)


_league_match_start = LeagueMatchStartService(_league_match_start_repo_scope, _start_simulation)


def get_match_runner() -> MatchRunner:
    return _match_runner


def get_friendly_start() -> FriendlyStartService:
    return _friendly_start


def get_league_match_start() -> LeagueMatchStartService:
    return _league_match_start
