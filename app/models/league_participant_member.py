import enum

from sqlalchemy import (
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MemberRole(str, enum.Enum):
    forward = "forward"
    midfield = "midfield"
    defense = "defense"
    substitute = "substitute"


class LeagueParticipantMember(Base):
    """Un integrante del equipo con el que un usuario juega una liga."""

    __tablename__ = "league_participant_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["league_id", "user_id"],
            ["league_participants.league_id", "league_participants.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("league_id", "user_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    behavior_id: Mapped[int] = mapped_column(ForeignKey("behaviors.id"), nullable=False)
    role: Mapped[MemberRole] = mapped_column(
        Enum(
            MemberRole,
            name="member_role",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )