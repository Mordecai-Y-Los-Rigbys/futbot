from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SessionLeagueAccess(Base):
    """Desbloqueo independiente de la inscripción, por sesión y liga."""

    __tablename__ = "session_league_access"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True, index=True
    )
