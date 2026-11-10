from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.behavior import BehaviorUsage
from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.models.behavior import Behavior, BehaviorType
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.team_member import TeamMember
from app.repositories.behavior_abstract import (
    AbstractBehaviorRepository,
    BehaviorData,
    CreateBehaviorData,
    DuplicateBehaviorNameError,
    UpdateBehaviorData,
)

ACTIVE_LEAGUE_STATUSES = (LeagueStatus.preparation, LeagueStatus.started)
UNFINISHED_MATCH_STATUSES = (MatchStatus.scheduled, MatchStatus.started)


class SqlAlchemyBehaviorRepository(AbstractBehaviorRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[BehaviorData], int]:
        filters = [Behavior.user_id == user_id, Behavior.deleted.is_(False)]
        if name:
            escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(Behavior.name.ilike(f"%{escaped}%", escape="\\"))

        total = self.db.scalar(select(func.count()).select_from(Behavior).where(*filters))

        rows = (
            self.db.execute(
                select(Behavior)
                .where(*filters)
                .order_by(Behavior.id.asc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return [BehaviorData.model_validate(r) for r in rows], total or 0

    def get_by_id(self, behavior_id: int) -> BehaviorData | None:
        record = self.db.get(Behavior, behavior_id)
        return BehaviorData.model_validate(record) if record is not None else None

    def create_many(self, user_id: int, behaviors: list[CreateBehaviorData]) -> list[BehaviorData]:
        records = [
            Behavior(user_id=user_id, name=b.name, code=b.code, type=b.type) for b in behaviors
        ]
        self.db.add_all(records)
        self.db.flush()
        return [BehaviorData.model_validate(r) for r in records]

    def name_taken(self, user_id: int, name: str, except_id: int | None = None) -> bool:
        query = select(Behavior.id).where(
            Behavior.user_id == user_id, Behavior.name == name, Behavior.deleted.is_(False)
        )
        if except_id is not None:
            query = query.where(Behavior.id != except_id)
        return self.db.scalar(query) is not None

    def create(self, user_id: int, data: CreateBehaviorData) -> BehaviorData:
        record = Behavior(user_id=user_id, name=data.name, code=data.code, type=data.type)
        self.db.add(record)
        try:
            self.db.commit()
        except IntegrityError as error:
            # La restricción única (user_id, name) frena a dos requests simultáneos
            # que pasaron el chequeo de name_taken con el mismo nombre.
            self.db.rollback()
            raise DuplicateBehaviorNameError() from error
        return BehaviorData.model_validate(record)

    def update(self, behavior_id: int, data: UpdateBehaviorData) -> BehaviorData | None:
        # Un solo UPDATE: si el behavior se eliminó después de leerlo, no toca ninguna fila.
        query = (
            update(Behavior)
            .where(Behavior.id == behavior_id, Behavior.deleted.is_(False))
            .values(name=data.name, code=data.code)
            .returning(Behavior)
        )
        try:
            record = self.db.execute(query).scalar_one_or_none()
            result = BehaviorData.model_validate(record) if record is not None else None
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise DuplicateBehaviorNameError() from error
        return result

    def usage(self, behavior_id: int) -> BehaviorUsage | None:
        active_leagues = select(League.id).where(League.status.in_(ACTIVE_LEAGUE_STATUSES))
        in_league_team = or_(
            exists().where(
                TeamMember.behavior_id == behavior_id,
                TeamMember.league_id.in_(active_leagues),
            ),
            exists().where(
                LeagueParticipant.coach_behavior_id == behavior_id,
                LeagueParticipant.league_id.in_(active_leagues),
            ),
        )
        # Los equipos con match_id son los de los amistosos.
        in_match = exists().where(
            TeamMember.behavior_id == behavior_id,
            TeamMember.match_id == Match.id,
            Match.status.in_(UNFINISHED_MATCH_STATUSES),
        )
        league_team, match = self.db.execute(select(in_league_team, in_match)).one()
        if league_team:
            return BehaviorUsage.league_team
        if match:
            return BehaviorUsage.match
        return None

    def delete_if_unused(self, behavior_id: int) -> BehaviorUsage | None:
        # FOR UPDATE espera a que terminen los requests que están armando un equipo
        # con este behavior (owned_behavior_ids y behavior_types lo bloquean), así
        # el chequeo de uso ya ve ese equipo.
        locked = self.db.scalar(
            select(Behavior.id)
            .where(Behavior.id == behavior_id, Behavior.deleted.is_(False))
            .with_for_update()
        )
        usage = self.usage(behavior_id)
        if locked is not None and usage is None:
            self.db.execute(update(Behavior).where(Behavior.id == behavior_id).values(deleted=True))
        self.db.commit()
        return usage

    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        return set(self.db.scalars(_lock_owned(select(Behavior.id), user_id, ids)))

    def behavior_types(self, user_id: int, ids: list[int]) -> dict[int, BehaviorType]:
        if not ids:
            return {}
        rows = self.db.execute(_lock_owned(select(Behavior.id, Behavior.type), user_id, ids)).all()
        return {behavior_id: BehaviorType(kind) for behavior_id, kind in rows}


def _lock_owned(query, user_id: int, ids: list[int]):
    """Behaviors no eliminados del usuario entre `ids`, bloqueados con FOR KEY SHARE.

    Ese bloqueo no frena a otros que arman equipos ni a PUT /behaviors/{id}, pero
    sí al FOR UPDATE de delete_if_unused, hasta que esta transacción termine.
    """
    return query.where(
        Behavior.user_id == user_id, Behavior.id.in_(ids), Behavior.deleted.is_(False)
    ).with_for_update(key_share=True)
