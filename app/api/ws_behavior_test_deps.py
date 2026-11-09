from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.database import SessionLocal
from app.repositories.behavior_test_lineup_sqlalchemy import SqlAlchemyBehaviorTestLineupRepository
from app.repositories.behavior_test_token_sqlalchemy import SqlAlchemyBehaviorTestTokenRepository
from app.services.behavior_test_handshake import BehaviorTestHandshakeService
from app.services.behavior_test_runner import BehaviorTestRunner
from app.services.behavior_test_slots import BehaviorTestSlots

# Únicos del proceso, como el registro de conexiones de partidos.
_slots = BehaviorTestSlots()
_runner = BehaviorTestRunner()


@contextmanager
def _handshake_service_scope() -> Iterator[BehaviorTestHandshakeService]:
    # Sesión de DB de vida corta, como en el partido: no queda abierta toda la prueba.
    with SessionLocal() as db:
        yield BehaviorTestHandshakeService(
            SqlAlchemyBehaviorTestTokenRepository(db),
            SqlAlchemyBehaviorTestLineupRepository(db),
        )


def get_behavior_test_handshake_scope() -> (
    Callable[[], ContextManager[BehaviorTestHandshakeService]]
):
    return _handshake_service_scope


def get_behavior_test_slots() -> BehaviorTestSlots:
    return _slots


def get_behavior_test_runner() -> BehaviorTestRunner:
    return _runner
