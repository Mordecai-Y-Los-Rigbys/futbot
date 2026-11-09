from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator

from app.config import allowed_origins
from app.database import SessionLocal
from app.repositories.league_access_sqlalchemy import SqlAlchemyLeagueAccessRepository
from app.repositories.league_participants_abstract import LeagueParticipantsState
from app.repositories.league_participants_sqlalchemy import SqlAlchemyLeagueParticipantsRepository
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.services.league_participants_handshake import LeagueParticipantsHandshakeService
from app.services.league_participants_manager import LeagueParticipantsManager
from app.services.league_participants_notifier import LeagueParticipantsNotifier
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
