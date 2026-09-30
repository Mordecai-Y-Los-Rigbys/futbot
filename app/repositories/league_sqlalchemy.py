from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
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