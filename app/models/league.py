from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.league import LeagueStatus
from app.models.user import User


class League(Base):
    __tablename__ = "leagues"

    __table_args__ = (
        CheckConstraint(
            "NOT private OR password IS NOT NULL",
            name="check_private_league_has_password",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[LeagueStatus] = mapped_column(
        Enum(
            LeagueStatus,
            name="league_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=LeagueStatus.preparation,
    )
    min_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    match_duration: Mapped[int] = mapped_column(Integer, nullable=False)  # minutos
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password: Mapped[str | None] = mapped_column(String(72), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    creator: Mapped[User] = relationship(User)
