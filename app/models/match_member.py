from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.league_participant_member import MemberRole


class MatchMember(Base):
    """Un integrante del equipo con el que un usuario juega un partido."""

    __tablename__ = "match_members"
    __table_args__ = (UniqueConstraint("match_id", "user_id", "player_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    behavior_id: Mapped[int] = mapped_column(ForeignKey("behaviors.id"), nullable=False)
    role: Mapped[MemberRole] = mapped_column(
        Enum(
            MemberRole,
            name="member_role",  # mismo tipo que league_participant_members
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )