from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.domain.team_member import MemberRole
from app.models.behavior import Behavior
from app.models.match import Match
from app.models.player import Player
from app.models.substitution import AppliedSubstitution, Substitution
from app.models.team_member import TeamMember
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    AppliedSwap,
    SubstitutionData,
)
from app.repositories.team_abstract import StarterData

_STARTER_ROLES = (MemberRole.forward, MemberRole.midfield, MemberRole.defense)


def _same_team(a: TeamMember, b: TeamMember) -> bool:
    return (
        a.user_id == b.user_id and a.league_id == b.league_id and a.match_id == b.match_id
    )


class SqlAlchemySubstitutionRepository(AbstractSubstitutionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_match(self, match_id: int) -> list[SubstitutionData]:
        return self._list(Substitution, match_id)

    def list_applied_by_match(self, match_id: int) -> list[SubstitutionData]:
        return self._list(AppliedSubstitution, match_id)

    def _list(self, model, match_id: int) -> list[SubstitutionData]:
        out_member = aliased(TeamMember)
        in_member = aliased(TeamMember)
        out_player = aliased(Player)
        in_player = aliased(Player)

        rows = self.db.execute(
            select(model.user_id, out_player.name, in_player.name)
            .select_from(model)
            .join(out_member, out_member.id == model.member_out_id)
            .join(out_player, out_player.id == out_member.player_id)
            .join(in_member, in_member.id == model.member_in_id)
            .join(in_player, in_player.id == in_member.player_id)
            .where(model.match_id == match_id)
            .order_by(model.user_id.asc())
        ).all()
        return [
            SubstitutionData(user_id=u, starter_name=out, substitute_name=inn)
            for u, out, inn in rows
        ]

    def apply_pending(self, match_id: int) -> list[AppliedSwap]:
        # El lock serializa con los PUT de este partido (el trigger de
        # `substitutions` toma el mismo lock) y con otra pausa.
        match = self.db.execute(
            select(Match.user_1_id).where(Match.id == match_id).with_for_update()
        ).one_or_none()
        if match is None:
            self.db.rollback()
            return []
        user_1_id = match[0]

        pending = self.db.scalars(
            select(Substitution)
            .where(Substitution.match_id == match_id)
            .order_by(Substitution.user_id.asc())
        ).all()
        self.db.execute(delete(AppliedSubstitution).where(AppliedSubstitution.match_id == match_id))

        swaps: list[AppliedSwap] = []
        for sub in pending:
            member_out = self.db.get(TeamMember, sub.member_out_id)
            member_in = self.db.get(TeamMember, sub.member_in_id)
            if (
                member_out is None
                or member_in is None
                or member_out.user_id != sub.user_id
                or not _same_team(member_out, member_in)
                or member_out.role not in _STARTER_ROLES
                or member_in.role is not MemberRole.substitute
            ):
                continue  # ya no es válida: se descarta

            role = member_out.role
            member_out.role = MemberRole.substitute
            member_in.role = role
            self.db.add(
                AppliedSubstitution(
                    match_id=match_id,
                    user_id=sub.user_id,
                    member_in_id=member_in.id,
                    member_out_id=member_out.id,
                )
            )
            player = self.db.get(Player, member_in.player_id)
            behavior = self.db.get(Behavior, member_in.behavior_id)
            swaps.append(
                AppliedSwap(
                    club="club1" if sub.user_id == user_1_id else "club2",
                    out_player_id=member_out.player_id,
                    incoming=StarterData(
                        player_id=player.id,
                        role=role,
                        power=player.power,
                        agility=player.agility,
                        control=player.control,
                        strength=player.strength,
                        speed=player.speed,
                        behavior_code=behavior.code,
                    ),
                )
            )

        self.db.execute(delete(Substitution).where(Substitution.match_id == match_id))
        self.db.commit()
        return swaps

    def upsert(
        self, match_id: int, user_id: int, member_in_id: int, member_out_id: int
    ) -> None:
        # INSERT .. ON CONFLICT hace atómico el reemplazo incluso ante PUT concurrentes.
        statement = pg_insert(Substitution).values(
            match_id=match_id,
            user_id=user_id,
            member_in_id=member_in_id,
            member_out_id=member_out_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[Substitution.match_id, Substitution.user_id],
            set_={
                "member_in_id": statement.excluded.member_in_id,
                "member_out_id": statement.excluded.member_out_id,
            },
        )
        try:
            self.db.execute(statement)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
