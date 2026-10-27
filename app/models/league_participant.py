from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LeagueParticipant(Base):
    """Un usuario inscripto en una liga (una fila por usuario, incluido el creador)."""

    __tablename__ = "league_participants"

    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    # Behavior del director técnico del equipo. NULL: el equipo no tiene DT
    # (coachBehaviorId es opcional, convención 10).
    coach_behavior_id: Mapped[int | None] = mapped_column(ForeignKey("behaviors.id"), nullable=True)
