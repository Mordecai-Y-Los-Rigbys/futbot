from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.session_league_unlock import SessionLeagueUnlock
from app.repositories.league_access_abstract import LeagueAccessInfo


class SqlAlchemyLeagueAccessRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_league(self, league_id: int) -> LeagueAccessInfo | None:
        row = self.db.execute(
            select(League.id, League.creator_id, League.private, League.password).where(
                League.id == league_id
            )
        ).one_or_none()
        return LeagueAccessInfo(*row) if row is not None else None

    def is_participant(self, league_id: int, user_id: int) -> bool:
        return (
            self.db.scalar(
                select(LeagueParticipant.user_id).where(
                    LeagueParticipant.league_id == league_id,
                    LeagueParticipant.user_id == user_id,
                )
            )
            is not None
        )

    def is_unlocked(self, session_id: str, league_id: int) -> bool:
        return (
            self.db.scalar(
                select(SessionLeagueUnlock.league_id).where(
                    SessionLeagueUnlock.session_id == session_id,
                    SessionLeagueUnlock.league_id == league_id,
                )
            )
            is not None
        )

    def unlock(self, session_id: str, league_id: int) -> None:
        if not self.is_unlocked(session_id, league_id):
            # La PK compuesta evita duplicados incluso con solicitudes concurrentes.
            try:
                with self.db.begin_nested():
                    self.db.add(SessionLeagueUnlock(session_id=session_id, league_id=league_id))
                    self.db.flush()
            except IntegrityError:
                if not self.is_unlocked(session_id, league_id):
                    raise  # No ocultar errores de FK u otras restricciones.
        self.db.commit()
