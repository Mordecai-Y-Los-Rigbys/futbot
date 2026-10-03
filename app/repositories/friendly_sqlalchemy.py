from datetime import timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.league_participant_member import MemberRole
from app.models.match import Match, MatchStatus
from app.models.match_member import MatchMember
from app.models.player import Player
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    CreateFriendlyData,
    FriendlyClubData,
    FriendlyMatchData,
)


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
            self.db.add_all(
                MatchMember(
                    match_id=match.id,
                    user_id=data.creator_id,
                    player_id=m.player_id,
                    behavior_id=m.behavior_id,
                    role=MemberRole(m.role),
                )
                for m in data.members
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(match)
        created_at = match.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return FriendlyMatchData(
            id=match.id,
            name=match.name,
            status=match.status.value,
            club1=FriendlyClubData(
                id=match.user_1.id,
                username=match.user_1.username,
                club_name=match.user_1.club_name,
            ),
            created_at=created_at,
        )
