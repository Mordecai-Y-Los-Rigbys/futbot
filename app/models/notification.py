from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    """Aviso a un participante de que terminó un partido de su liga o la liga.

    `league_match_id` es NULL en las de fin de liga.
    """

    __tablename__ = "notifications"

    __table_args__ = (
        # Las más recientes de cada usuario (ORDER BY created_at DESC, id DESC).
        Index("ix_notifications_user_created", "user_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    league_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=True
    )
    # server_default: las filas se insertan con INSERT ... SELECT.
    seen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
