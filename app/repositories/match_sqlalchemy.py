from sqlalchemy import func, select, true, update
from sqlalchemy.orm import Session, aliased

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.models.league import League
from app.models.match import Match
from app.models.user import User
from app.repositories.match_abstract import (
    AbstractMatchRepository,
    MatchSetupData,
    MatchStateData,
    MatchPlayersData,
    PenaltyShootoutData,
)


class SqlAlchemyMatchRepository(AbstractMatchRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_state(self, match_id: int) -> MatchStateData | None:
        record = self.db.get(Match, match_id)
        if record is None:
            return None
        return MatchStateData(id=record.id, status=record.status.value)

    def get_setup_data(self, match_id: int) -> MatchSetupData | None:
        user_1 = aliased(User)
        user_2 = aliased(User)

        row = self.db.execute(
            select(
                Match.id,
                Match.league_id,
                Match.user_1_id,
                Match.user_2_id,
                user_1.club_name.label("club_1_name"),
                user_2.club_name.label("club_2_name"),
                func.coalesce(League.allow_draws, true()).label("allow_draws"),
            )
            .join(user_1, user_1.id == Match.user_1_id)
            .outerjoin(League, League.id == Match.league_id)
            .outerjoin(user_2, user_2.id == Match.user_2_id)  # outer: puede no haber rival
            .where(Match.id == match_id)
        ).one_or_none()

        if row is None:
            return None

        return MatchSetupData(
            id=row.id,
            league_id=row.league_id,
            user_1_id=row.user_1_id,
            user_2_id=row.user_2_id,
            club_1_name=row.club_1_name,
            club_2_name=row.club_2_name,
            allow_draws=row.allow_draws,
        )

    def mark_started(self, match_id: int) -> None:
        self.db.execute(
            update(Match)
            .where(Match.id == match_id, Match.status == MatchStatus.scheduled)
            .values(status=MatchStatus.started)
        )
        self.db.commit()

    def finish(
        self,
        match_id: int,
        score_1: int,
        score_2: int,
        penalties: PenaltyShootoutData | None = None,
    ) -> bool:
        shootout = {}
        if penalties is not None:
            shootout = {
                "penalty_score_1": penalties.score_1,
                "penalty_score_2": penalties.score_2,
                "penalty_winner": penalties.winner,
                "penalty_kicks": penalties.kicks,
            }
        league_id = self.db.scalar(select(Match.league_id).where(Match.id == match_id))
        try:
            if league_id is not None:
                # Bloquea la liga: si dos partidos terminan a la vez, el segundo
                # espera al primero y, al contar los pendientes, ya lo ve terminado.
                self.db.execute(select(League.id).where(League.id == league_id).with_for_update())

            self.db.execute(
                update(Match)
                .where(Match.id == match_id)
                .values(status=MatchStatus.finished, score_1=score_1, score_2=score_2, **shootout)
            )
            league_finished = league_id is not None and self._finish_league_if_done(league_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return league_finished

    def _finish_league_if_done(self, league_id: int) -> bool:
        pending = (
            select(Match.id)
            .where(Match.league_id == league_id, Match.status != MatchStatus.finished)
            .exists()
        )
        result = self.db.execute(
            update(League)
            .where(League.id == league_id, League.status == LeagueStatus.started, ~pending)
            .values(status=LeagueStatus.finished)
        )
        return result.rowcount == 1

    def save_seed(self, match_id: int, seed: int) -> None:
        self.db.execute(update(Match).where(Match.id == match_id).values(seed=seed))
        self.db.commit()

    def get_players(self, match_id: int) -> MatchPlayersData | None:
        row = self.db.execute(
            select(Match.id, Match.status, Match.league_id, Match.user_1_id, Match.user_2_id).where(
                Match.id == match_id
            )
        ).first()
        if row is None:
            return None
        return MatchPlayersData(
            id=row.id,
            status=row.status,
            league_id=row.league_id,
            user_1_id=row.user_1_id,
            user_2_id=row.user_2_id,
        )
