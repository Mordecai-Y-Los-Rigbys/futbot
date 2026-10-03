from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, func, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.match import MatchStatus
from app.models.league import League
from app.models.user import User
from app.database import Base


class Match(Base):
    """Un partido, de liga o amistoso.

    - Partido de liga: `league_id` apunta a la liga y `scheduled_at` es la fecha
      del fixture. Los dos usuarios se conocen desde que se genera el fixture.
    - Partido amistoso: `league_id` es NULL. Se crea junto con el amistoso, con
      el creador como usuario 1 y sin usuario 2 (`user_2_id` NULL) hasta que un
      rival se une. No tiene fecha programada.

    El resultado (`score_1`/`score_2`) se persiste recién al terminar el
    partido: mientras se juega, el marcador vive en la simulación (campos
    `score1`/`score2` de cada `tick`).

    El "estado de espera" del amistoso (`waiting`/`starting`) es del amistoso,
    no del partido: para el partido sigue siendo `scheduled` hasta que arranca.
    """

    __tablename__ = "matches"

    __table_args__ = (
        # Un usuario no puede jugar contra sí mismo.
        CheckConstraint(
            "user_2_id IS NULL OR user_1_id <> user_2_id",
            name="ck_matches_distinct_clubs",
        ),
        # Solo un partido sin arrancar o cancelado puede no tener rival.
        CheckConstraint(
            "status IN ('scheduled', 'cancelled') OR user_2_id IS NOT NULL",
            name="ck_matches_started_has_rival",
        ),
        # El resultado se guarda completo o no se guarda.
        CheckConstraint(
            "(score_1 IS NULL) = (score_2 IS NULL)",
            name="ck_matches_scores_both_or_none",
        ),
        # Hay resultado si y solo si el partido terminó (`result: null` si
        # status != finished, según el OpenAPI).
        CheckConstraint(
            "(status = 'finished') = (score_1 IS NOT NULL)",
            name="ck_matches_result_iff_finished",
        ),
        CheckConstraint(
            "score_1 >= 0 AND score_2 >= 0",
            name="ck_matches_scores_non_negative",
        ),
        # Todo partido de liga tiene fecha en el fixture (`date` requerida).
        CheckConstraint(
            "league_id IS NULL OR scheduled_at IS NOT NULL",
            name="ck_matches_league_match_has_date",
        ),
        # Un partido de liga siempre tiene rival: se define al generar el fixture.
        CheckConstraint(
            "league_id IS NULL OR user_2_id IS NOT NULL",
            name="ck_matches_league_match_has_rival",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int | None] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_1_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    user_2_id: Mapped[int | None] = mapped_column(
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
    score_1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_2: Mapped[int | None] = mapped_column(Integer, nullable=True)

    league: Mapped[League | None] = relationship(League)
    user_1: Mapped[User] = relationship(User, foreign_keys=[user_1_id])
    user_2: Mapped[User | None] = relationship(User, foreign_keys=[user_2_id])
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )