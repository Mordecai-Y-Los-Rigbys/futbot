from datetime import timezone

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.league import LeagueStatus
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.session_league_unlock import SessionLeagueUnlock
from app.models.team_member import TeamMember
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    CreateLeagueData,
    LeagueCreatorData,
    LeagueListItemData,
    LeaguePageData,
    LeagueLeaveInfo,
    LeagueDetailData,
    JoinLeagueData,
    JoinLeagueStateConflict,
    LeagueJoinState,
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
            avatar=record.creator.avatar,
        ),
        status=getattr(record.status, "value", record.status),
        participants_count=participants_count,
        max_participants=record.max_participants,
        private=record.private,
        created_at=created_at,
        allow_draws=record.allow_draws,
    )


class SqlAlchemyLeagueRepository(AbstractLeagueRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_page(self, name: str | None, offset: int, limit: int) -> LeaguePageData:
        filters = []
        if name:
            filters.append(League.name.ilike(f"%{_escape_like(name)}%", escape="\\"))

        total = self.db.scalar(select(func.count()).select_from(League).where(*filters))

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
                TeamMember(
                    league_id=league.id,
                    match_id=None,  # el CHECK exige que exactamente uno esté seteado
                    user_id=data.creator_id,
                    player_id=m.player_id,
                    behavior_id=m.behavior_id,
                    role=m.role,
                )
                for m in data.members
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(league)
        return _to_data(league, participants_count=1)

    def get_match_duration_minutes(self, league_id: int) -> int | None:
        # scalar() devuelve None si la liga no existe
        return self.db.scalar(select(League.match_duration).where(League.id == league_id))
    
    def get_leave_info(self, league_id: int) -> LeagueLeaveInfo | None:
        row = self.db.execute(
            select(League.status, League.creator_id).where(League.id == league_id)
        ).one_or_none()
        if row is None:
            return None
        return LeagueLeaveInfo(status=row.status, creator_id=row.creator_id)

    def is_participant(self, league_id: int, user_id: int) -> bool:
        found = self.db.scalar(
            select(LeagueParticipant.user_id).where(
                LeagueParticipant.league_id == league_id,
                LeagueParticipant.user_id == user_id,
            )
        )
        return found is not None

    def remove_participant(self, league_id: int, user_id: int) -> None:
        try:
            # Explícito, sin depender del ON DELETE CASCADE (en SQLite requiere PRAGMA)
            self.db.execute(
                delete(TeamMember).where(
                    TeamMember.league_id == league_id, TeamMember.user_id == user_id
                )
            )
            self.db.execute(
                delete(LeagueParticipant).where(
                    LeagueParticipant.league_id == league_id,
                    LeagueParticipant.user_id == user_id,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
    
    def get_detail(self, league_id: int, user_id: int) -> LeagueDetailData | None:
        participants_count = (
            select(func.count(func.distinct(LeagueParticipant.user_id)))
            .where(LeagueParticipant.league_id == League.id)
            .correlate(League)
            .scalar_subquery()
        )
        joined = (
            select(LeagueParticipant.user_id)
            .where(
                LeagueParticipant.league_id == League.id,
                LeagueParticipant.user_id == user_id,
            )
            .correlate(League)
            .exists()
        )
        row = self.db.execute(
            select(League, participants_count, joined)
            .options(joinedload(League.creator))
            .where(League.id == league_id)
        ).first()
        if row is None:
            return None

        league, count, is_joined = row
        return LeagueDetailData(
            **_to_data(league, count).model_dump(),
            min_participants=league.min_participants,
            joined=bool(is_joined),
        )

    # ------------------------------------------------------------------
    # Inscripción (POST /leagues/{id}/participants)
    # ------------------------------------------------------------------

    def _join_state(self, league: League, user_id: int) -> LeagueJoinState:
        count = self.db.scalar(
            select(func.count())
            .select_from(LeagueParticipant)
            .where(LeagueParticipant.league_id == league.id)
        )
        is_participant = self.db.scalar(
            select(
                exists().where(
                    LeagueParticipant.league_id == league.id,
                    LeagueParticipant.user_id == user_id,
                )
            )
        )
        return LeagueJoinState(
            private=league.private,
            password=league.password,
            status=league.status,
            max_participants=league.max_participants,
            participants_count=count or 0,
            is_participant=bool(is_participant),
        )

    def get_join_state(self, league_id: int, user_id: int) -> LeagueJoinState | None:
        league = self.db.get(League, league_id)
        return None if league is None else self._join_state(league, user_id)

    def join(self, data: JoinLeagueData) -> JoinLeagueStateConflict | None:
        try:
            # Bloquea la fila de la liga hasta el commit: dos inscripciones
            # simultáneas se serializan y la segunda ve a la primera al contar.
            # populate_existing: la liga ya puede estar en la sesión (la leyó
            # get_join_state) y hay que releer su estado, no usar el cacheado.
            # En SQLite FOR UPDATE se ignora (los tests de concurrencia usan Postgres).
            league = self.db.scalars(
                select(League)
                .where(League.id == data.league_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).one()

            conflict = self._join_state(league, data.user_id).conflict()
            if conflict is not None:
                self.db.rollback()
                return conflict

            self.db.add(
                LeagueParticipant(
                    league_id=data.league_id,
                    user_id=data.user_id,
                    coach_behavior_id=data.coach_behavior_id,
                )
            )
            self.db.flush()  # el participante debe existir antes que sus miembros (FK)
            self.db.add_all(
                TeamMember(
                    league_id=data.league_id,
                    match_id=None,
                    user_id=data.user_id,
                    player_id=m.player_id,
                    behavior_id=m.behavior_id,
                    role=m.role,
                )
                for m in data.members
            )
            if data.unlock_session and (
                self.db.get(SessionLeagueUnlock, (data.session_id, data.league_id)) is None
            ):
                self.db.add(
                    SessionLeagueUnlock(session_id=data.session_id, league_id=data.league_id)
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return None
