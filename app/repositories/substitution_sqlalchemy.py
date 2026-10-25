from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.player import Player
from app.models.substitution import Substitution
from app.models.team_member import TeamMember
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    FirstSubstitutionData,
)


class SqlAlchemySubstitutionRepository(AbstractSubstitutionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_first_per_team(self, match_id: int) -> list[FirstSubstitutionData]:
        out_member = aliased(TeamMember)
        in_member = aliased(TeamMember)
        out_player = aliased(Player)
        in_player = aliased(Player)

        first_ids = (
            select(func.min(Substitution.id))
            .join(TeamMember, TeamMember.id == Substitution.member_out_id)
            .where(Substitution.match_id == match_id)
            .group_by(TeamMember.user_id)
        )
        rows = self.db.execute(
            select(out_member.user_id, out_player.name, in_player.name)
            .select_from(Substitution)
            .join(out_member, out_member.id == Substitution.member_out_id)
            .join(out_player, out_player.id == out_member.player_id)
            .join(in_member, in_member.id == Substitution.member_in_id)
            .join(in_player, in_player.id == in_member.player_id)
            .where(Substitution.id.in_(first_ids))
            .order_by(Substitution.id.asc())
        ).all()
        return [
            FirstSubstitutionData(user_id=u, starter_name=out, substitute_name=inn)
            for u, out, inn in rows
        ]