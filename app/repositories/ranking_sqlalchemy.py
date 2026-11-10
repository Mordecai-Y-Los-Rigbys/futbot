from sqlalchemy import and_, case, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.user import User
from app.repositories.ranking_abstract import AbstractRankingRepository, ClubRankingData

_TOTALS = ("won_regular", "won_penalties", "drawn", "lost", "goals_for", "goals_against")


def _flag(condition):
    return case((condition, 1), else_=0)

def _side(me: int):
    """Los partidos vistos desde el club `me` (1 o 2): una fila por partido y por club."""
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
            _flag(or_(mine < theirs, and_(tied, Match.penalty_winner == opponent))).label("lost"),
        )
        .select_from(Match)
        .join(League, League.id == Match.league_id)
    )

def _sides(*conditions):
    """Partidos finalizados que cumplen `conditions`, vistos desde ambos clubes."""
    return union_all(
        *(_side(me).where(Match.status == MatchStatus.finished, *conditions) for me in (1, 2))
    ).subquery("sides")

def _totals(sides):
    return [func.coalesce(func.sum(sides.c[name]), 0) for name in _TOTALS]

def _to_data(row) -> ClubRankingData:
    club_id, name, avatar, *totals = row
    return ClubRankingData(
        club_id=club_id,
        name=name,
        avatar=avatar,
        **{field: int(value) for field, value in zip(_TOTALS, totals)},
    )
    
    
class SqlAlchemyRankingRepository(AbstractRankingRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_club_totals(self) -> list[ClubRankingData]:
        sides = _sides(League.private.is_(False), League.status != LeagueStatus.preparation)
        rows = self.db.execute(
            select(User.id, User.club_name, User.avatar, *_totals(sides))
            .select_from(sides)
            .join(User, User.id == sides.c.club_id)
            .group_by(User.id, User.club_name, User.avatar)
        ).all()
        return [_to_data(r) for r in rows]

    def list_league_club_totals(self, league_id: int) -> list[ClubRankingData]:
        sides = _sides(Match.league_id == league_id)
        rows = self.db.execute(
            select(User.id, User.club_name, User.avatar, *_totals(sides))
            .select_from(LeagueParticipant)
            .join(User, User.id == LeagueParticipant.user_id)
            .outerjoin(sides, sides.c.club_id == User.id)
            .where(LeagueParticipant.league_id == league_id)
            .group_by(User.id, User.club_name, User.avatar)
        ).all()
        return [_to_data(r) for r in rows]

    def get_league_status(self, league_id: int) -> LeagueStatus | None:
        return self.db.scalar(select(League.status).where(League.id == league_id))