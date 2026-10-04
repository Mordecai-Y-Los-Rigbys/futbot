from datetime import timezone

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.domain.team_member import MemberRole
from app.models.behavior import Behavior
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.team_member import TeamMember
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    CreateFriendlyData,
    CreateFriendlyMemberData,
    FriendlyClubData,
    FriendlyMatchData,
    FriendlyPageData,
    FriendlyJoinState,
    JoinFriendlyData,
)
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository


def _escape_like(value: str) -> str:
    # El orden importa: primero la barra, después los comodines.
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _friendly_team(
    match_id: int, user_id: int, members: list[CreateFriendlyMemberData]
) -> list[TeamMember]:
    """Equipo de un usuario en un amistoso: filas de team_members con match_id
    (y sin league_id: el CHECK exige que haya exactamente un dueño)."""
    return [
        TeamMember(
            league_id=None,
            match_id=match_id,
            user_id=user_id,
            player_id=m.player_id,
            behavior_id=m.behavior_id,
            role=MemberRole(m.role),
        )
        for m in members
    ]


def _utc(created_at):
    # DateTime naive -> UTC, como en los otros repos.
    return created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at


def _club(user) -> FriendlyClubData:
    return FriendlyClubData(id=user.id, username=user.username, club_name=user.club_name)


class SqlAlchemyFriendlyRepository(AbstractFriendlyRepository):
    def __init__(self, db: Session):
        self.db = db

    def user_is_playing(self, user_id: int) -> bool:
        stmt = (
            select(Match.id)
            .where(
                or_(Match.user_1_id == user_id, Match.user_2_id == user_id),
                or_(
                    Match.status == MatchStatus.started,
                    and_(
                        Match.status == MatchStatus.scheduled,
                        Match.league_id.is_(None),
                    ),
                ),
            )
            .limit(1)
        )
        return self.db.scalar(stmt) is not None

    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]:
        rows = self.db.scalars(
            select(Player.id).where(Player.user_id == user_id, Player.id.in_(ids))
        )
        return set(rows)

    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        rows = self.db.scalars(
            select(Behavior.id).where(
                Behavior.user_id == user_id, Behavior.id.in_(ids)
            )
        )
        return set(rows)

    def create_with_team(self, data: CreateFriendlyData) -> FriendlyMatchData:
        match = Match(
            user_1_id=data.creator_id,
            name=data.name,
            status=MatchStatus.scheduled,
        )
        try:
            self.db.add(match)
            self.db.flush()  # obtiene match.id
            self.db.add_all(_friendly_team(match.id, data.creator_id, data.members))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(match)
        return FriendlyMatchData(
            id=match.id,
            name=match.name,
            status=match.status.value,
            club1=_club(match.user_1),
            created_at=_utc(match.created_at),
        )

    def list_waiting_page(
        self, exclude_user_id: int, name: str | None, offset: int, limit: int
    ) -> FriendlyPageData:
        filters = [
            SqlAlchemyMatchExpiryRepository.is_waiting_friendly(),
            Match.user_1_id != exclude_user_id,
        ]
        if name:
            filters.append(Match.name.ilike(f"%{_escape_like(name)}%", escape="\\"))

        total = self.db.scalar(select(func.count()).select_from(Match).where(*filters))

        matches = self.db.scalars(
            select(Match)
            .options(joinedload(Match.user_1))  # creador en la misma consulta
            .where(*filters)
            .order_by(Match.id.asc())
            .offset(offset)
            .limit(limit)
        ).all()

        items = [
            FriendlyMatchData(
                id=m.id,
                name=m.name,
                status=m.status.value,
                club1=_club(m.user_1),
                created_at=_utc(m.created_at),
            )
            for m in matches
        ]
        return FriendlyPageData(items=items, total=total)

    def get_friendly_state(self, match_id: int) -> FriendlyJoinState | None:
        row = self.db.execute(
            select(Match.id, Match.user_1_id, Match.user_2_id, Match.status).where(
                Match.id == match_id, Match.league_id.is_(None)
            )
        ).first()
        if row is None:
            return None
        return FriendlyJoinState(
            id=row.id,
            creator_id=row.user_1_id,
            rival_id=row.user_2_id,
            status=row.status.value,
        )

    def join_friendly(self, data: JoinFriendlyData) -> FriendlyMatchData | None:
        try:
            result = self.db.execute(
                update(Match)
                .where(
                    Match.id == data.match_id,
                    SqlAlchemyMatchExpiryRepository.is_waiting_friendly(),
                    Match.user_1_id != data.user_id,
                )
                .values(user_2_id=data.user_id)
            )
            if result.rowcount != 1:  # lo ganó otro rival o el vencimiento
                self.db.rollback()
                return None
            self.db.add_all(_friendly_team(data.match_id, data.user_id, data.members))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        match = self.db.get(Match, data.match_id)
        self.db.refresh(match)
        return FriendlyMatchData(
            id=match.id,
            name=match.name,
            status=match.status.value,
            club1=_club(match.user_1),
            club2=_club(match.user_2),
            created_at=_utc(match.created_at),
        )