from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from app.models.behavior import Behavior
from app.models.player import Player
from app.models.substitution import Substitution
from app.models.team_member import MemberRole, TeamMember
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    AppliedSubstitution,
    SubstitutionData,
)
from app.repositories.team_abstract import StarterData


class SqlAlchemySubstitutionRepository(AbstractSubstitutionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_match(self, match_id: int) -> list[SubstitutionData]:
        out_member = aliased(TeamMember)
        in_member = aliased(TeamMember)
        out_player = aliased(Player)
        in_player = aliased(Player)

        rows = self.db.execute(
            select(Substitution.user_id, out_player.name, in_player.name)
            .select_from(Substitution)
            .join(out_member, out_member.id == Substitution.member_out_id)
            .join(out_player, out_player.id == out_member.player_id)
            .join(in_member, in_member.id == Substitution.member_in_id)
            .join(in_player, in_player.id == in_member.player_id)
            .where(Substitution.match_id == match_id)
            .order_by(Substitution.user_id.asc())
        ).all()
        return [
            SubstitutionData(user_id=u, starter_name=out, substitute_name=inn)
            for u, out, inn in rows
        ]

    def apply_by_match(self, match_id: int) -> list[AppliedSubstitution]:
        in_member = aliased(TeamMember)
        out_member = aliased(TeamMember)

        # Solo las que faltan aplicar: entra un suplente y sale un titular.
        # Si ya se aplicó, los roles están invertidos y no matchea.
        rows = self.db.execute(
            select(Substitution.user_id, in_member, out_member, Player, Behavior.code)
            .select_from(Substitution)
            .join(in_member, in_member.id == Substitution.member_in_id)
            .join(out_member, out_member.id == Substitution.member_out_id)
            .join(Player, Player.id == in_member.player_id)
            .join(Behavior, Behavior.id == in_member.behavior_id)
            .where(
                Substitution.match_id == match_id,
                in_member.role == MemberRole.substitute,
                out_member.role != MemberRole.substitute,
            )
            .order_by(Substitution.user_id.asc())
        ).all()

        applied = []
        for user_id, entering, leaving, player, behavior_code in rows:
            # Solo se intercambian los roles: cada uno conserva su behavior.
            entering.role, leaving.role = leaving.role, MemberRole.substitute
            applied.append(
                AppliedSubstitution(
                    user_id=user_id,
                    incoming=StarterData(
                        player_id=player.id,
                        role=entering.role,
                        power=player.power,
                        agility=player.agility,
                        control=player.control,
                        strength=player.strength,
                        speed=player.speed,
                        behavior_code=behavior_code,
                    ),
                )
            )
        self.db.commit()
        return applied

    def delete_by_match(self, match_id: int) -> int:
        result = self.db.execute(delete(Substitution).where(Substitution.match_id == match_id))
        self.db.commit()
        return result.rowcount

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
        self.db.execute(statement)
        self.db.commit()
