import enum

from sqlalchemy import (
    CheckConstraint,
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


class TeamMember(Base):
    """Un integrante del equipo de un usuario, en una liga o en un amistoso.

    - Equipo de liga: `league_id` + `user_id` (participante de esa liga).
    - Equipo de amistoso: `match_id` + `user_id`.
    Exactamente uno de `league_id` / `match_id` está seteado. El equipo de liga
    es el mismo para todos los partidos de esa liga: reasignar un behavior o
    sustituir actualiza estas filas, así que el cambio persiste al siguiente partido.
    """

    __tablename__ = "team_members"
    __table_args__ = (
        # Con league_id NULL (amistoso) esta FK no se evalúa (MATCH SIMPLE).
        ForeignKeyConstraint(
            ["league_id", "user_id"],
            ["league_participants.league_id", "league_participants.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(league_id IS NULL) <> (match_id IS NULL)",
            name="ck_team_members_exactly_one_owner",
        ),
        # Los NULL son distintos entre sí: cada UNIQUE solo aplica a su tipo.
        UniqueConstraint("league_id", "user_id", "player_id"),
        UniqueConstraint("match_id", "user_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
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