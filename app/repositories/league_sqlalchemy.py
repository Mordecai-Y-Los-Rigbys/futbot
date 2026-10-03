from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.league import LeagueStatus
from app.domain.league_participant_member import MemberRole
from app.models.behavior import Behavior
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.league_participant_member import LeagueParticipantMember
from app.models.player import Player
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    CreateLeagueData,
    LeagueCreatorData,
    LeagueListItemData,
    LeaguePageData,
)


def _escape_like(value: str) -> str:
    # El orden importa: primero la barra, después los comodines.
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_data(record: League, participants_count: int) -> LeagueListItemData:
    # Las columnas DateTime sin timezone vuelven "naive": es un detalle de
    # persistencia, así que se normaliza acá y el servicio siempre recibe
    # datetimes con timezone.
    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return LeagueListItemData(
        id=record.id,
        name=record.name,
        creator=LeagueCreatorData(
            id=record.creator.id,
            username=record.creator.username,
            club_name=record.creator.club_name,
        ),
        status=getattr(record.status, "value", record.status),
        participants_count=participants_count,
        max_participants=record.max_participants,
        private=record.private,
        created_at=created_at,
    )


class SqlAlchemyLeagueRepository(AbstractLeagueRepository):
    def __init__(self, db: Session):
        self.db = db

    def list_page(self, name: str | None, offset: int, limit: int) -> LeaguePageData:
        filters = []
        if name:
            filters.append(
                League.name.ilike(f"%{_escape_like(name)}%", escape="\\")
            )

        total = self.db.scalar(
            select(func.count()).select_from(League).where(*filters)
        )

        participants_count = (
            select(func.count(func.distinct(LeagueParticipant.user_id)))
            .select_from(LeagueParticipant)
            .where(LeagueParticipant.league_id == League.id)
            .correlate(League)
            .scalar_subquery()
        )

        stmt = (
            select(League, participants_count)
            .options(joinedload(League.creator))
            .where(*filters)
            .order_by(League.id.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()

        return LeaguePageData(
            items=[_to_data(league, count) for league, count in rows],
            total=total,
        )

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

    def create(self, data: CreateLeagueData) -> LeagueListItemData:
        league = League(
            name=data.name,
            creator_id=data.creator_id,
            status=LeagueStatus.preparation,
            min_participants=data.min_participants,
            max_participants=data.max_participants,
            match_duration=data.match_duration,
            private=data.private,
            password=data.password,
        )
        try:
            self.db.add(league)
            self.db.flush()  # obtiene league.id
            self.db.add(LeagueParticipant(league_id=league.id, user_id=data.creator_id))
            self.db.flush()  # el participante debe existir antes que sus miembros (FK)
            self.db.add_all(
                LeagueParticipantMember(
                    league_id=league.id,
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

        self.db.refresh(league)
        return _to_data(league, participants_count=1)