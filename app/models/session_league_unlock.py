from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SessionLeagueUnlock(Base):
    """Una liga privada desbloqueada en una sesión (convención 11).

    Dura lo que dura la sesión: al borrarse la sesión (log-out o vencimiento)
    se borran sus desbloqueos en cascada.
    """

    __tablename__ = "session_league_unlocks"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True
    )
