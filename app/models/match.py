import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.league import League
from app.models.user import User


class MatchStatus(str, enum.Enum):
    """Mismos valores que `MatchStatus` del OpenAPI."""

    scheduled = "scheduled"  # todavía no se jugó
    started = "started"  # se está jugando ahora
    finished = "finished"  # ya tiene resultado


class Match(Base):
    """Un partido, de liga o amistoso.

    - Partido de liga: `league_id` apunta a la liga y `scheduled_at` es la fecha
      del fixture. Local y visitante se conocen desde que se genera el fixture.
    - Partido amistoso: `league_id` es NULL. Se crea junto con el amistoso, con
      el creador como local y sin visitante (`away_user_id` NULL) hasta que un
      rival se une. No tiene fecha programada.

    El resultado (`home_score`/`away_score`) se persiste recién al terminar el
    partido: mientras se juega, el marcador vive en la simulación (campos
    `homeScore`/`awayScore` de cada `tick`).

    El "estado de espera" del amistoso (`waiting`/`starting`) es del amistoso,
    no del partido: para el partido sigue siendo `scheduled` hasta que arranca.
    """

    __tablename__ = "matches"

    __table_args__ = (
        # Un usuario no puede jugar contra sí mismo.
        CheckConstraint(
            "away_user_id IS NULL OR home_user_id <> away_user_id",
            name="ck_matches_distinct_clubs",
        ),
        # No puede arrancar ni terminar sin rival.
        CheckConstraint(
            "status = 'scheduled' OR away_user_id IS NOT NULL",
            name="ck_matches_started_has_rival",
        ),
        # El resultado se guarda completo o no se guarda.
        CheckConstraint(
            "(home_score IS NULL) = (away_score IS NULL)",
            name="ck_matches_scores_both_or_none",
        ),
        # Hay resultado si y solo si el partido terminó (`result: null` si
        # status != finished, según el OpenAPI).
        CheckConstraint(
            "(status = 'finished') = (home_score IS NOT NULL)",
            name="ck_matches_result_iff_finished",
        ),
        CheckConstraint(
            "home_score >= 0 AND away_score >= 0",
            name="ck_matches_scores_non_negative",
        ),
        # Todo partido de liga tiene fecha en el fixture (`date` requerida).
        CheckConstraint(
            "league_id IS NULL OR scheduled_at IS NOT NULL",
            name="ck_matches_league_match_has_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int | None] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=True, index=True
    )
    home_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    away_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(
            MatchStatus,
            name="match_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=MatchStatus.scheduled,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    league: Mapped[League | None] = relationship(League)
    home_user: Mapped[User] = relationship(User, foreign_keys=[home_user_id])
    away_user: Mapped[User | None] = relationship(User, foreign_keys=[away_user_id])