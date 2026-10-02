from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.database import SessionLocal
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.match_ws_token_sqlalchemy import SqlAlchemyMatchWsTokenRepository
from app.services.match_connection_manager import MatchConnectionManager
from app.services.match_handshake_service import MatchHandshakeService

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