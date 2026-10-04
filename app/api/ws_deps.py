from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.database import SessionLocal
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.match_ws_token_sqlalchemy import SqlAlchemyMatchWsTokenRepository
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository
from app.services.match_connection_manager import MatchConnectionManager
from app.services.match_handshake_service import MatchHandshakeService
from app.services.friendly_expiry import FriendlyExpiryService
from app.repositories.match_start_sqlalchemy import SqlAlchemyMatchStartRepository
from app.services.friendly_start import FriendlyStartService


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


def get_handshake_service_scope() -> Callable[
    [], ContextManager[MatchHandshakeService]
]:
    return _handshake_service_scope


@contextmanager
def _expiry_repo_scope():
    with SessionLocal() as db:
        yield SqlAlchemyMatchExpiryRepository(db)

_friendly_expiry = FriendlyExpiryService(
    _expiry_repo_scope, _connection_manager.close_match
)

def get_friendly_expiry() -> FriendlyExpiryService:
    return _friendly_expiry


@contextmanager
def _start_repo_scope():
    with SessionLocal() as db:
        yield SqlAlchemyMatchStartRepository(db)


# on_start=None: acá se engancha la simulación cuando exista.
_friendly_start = FriendlyStartService(_start_repo_scope)


def get_friendly_start() -> FriendlyStartService:
    return _friendly_start