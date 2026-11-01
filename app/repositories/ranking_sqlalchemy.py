from sqlalchemy import and_, case, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.models.league import League
from app.models.match import Match
from app.models.user import User
from app.repositories.ranking_abstract import AbstractRankingRepository, ClubRankingData


def _flag(condition):
    return case((condition, 1), else_=0)


def _side(me: int):
    """Los partidos finalizados de ligas públicas vistos desde el club `me`
    (1 o 2): una fila por partido y por club."""
    club = Match.user_1_id if me == 1 else Match.user_2_id
    mine, theirs = (Match.score_1, Match.score_2) if me == 1 else (Match.score_2, Match.score_1)
    opponent = 2 if me == 1 else 1
    tied = mine == theirs  # los penales solo cuentan si el juego terminó empatado
    return (
        select(
            club.label("club_id"),
            mine.label("goals_for"),
            theirs.label("goals_against"),
            _flag(mine > theirs).label("won_regular"),
            _flag(and_(tied, Match.penalty_winner == me)).label("won_penalties"),
            _flag(and_(tied, Match.penalty_winner.is_(None))).label("drawn"),
            _flag(
                or_(mine < theirs, and_(tied, Match.penalty_winner == opponent))
            ).label("lost"),
        )
        .select_from(Match)
        .join(League, League.id == Match.league_id)
        .where(
            Match.status == MatchStatus.finished,
            League.private.is_(False),
            League.status != LeagueStatus.preparation,
        )
    )


class SqlAlchemyRankingRepository(AbstractRankingRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_club_totals(self) -> list[ClubRankingData]:
        sides = union_all(_side(1), _side(2)).subquery("sides")
        rows = self.db.execute(
            select(
                User.id,
                User.club_name,
                User.avatar,
                func.sum(sides.c.won_regular),
                func.sum(sides.c.won_penalties),
                func.sum(sides.c.drawn),
                func.sum(sides.c.lost),
                func.sum(sides.c.goals_for),
                func.sum(sides.c.goals_against),
            )
            .select_from(sides)
            .join(User, User.id == sides.c.club_id)
            .group_by(User.id, User.club_name, User.avatar)
        ).all()
        return [
            ClubRankingData(
                club_id=r[0],
                name=r[1],
                avatar=r[2],
                won_regular=int(r[3]),
                won_penalties=int(r[4]),
                drawn=int(r[5]),
                lost=int(r[6]),
                goals_for=int(r[7]),
                goals_against=int(r[8]),
            )
            for r in rows
        ]