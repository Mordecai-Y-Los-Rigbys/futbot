from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.substitution import Substitution
from app.models.team_member import TeamMember
from app.repositories.substitution_abstract import AbstractSubstitutionRepository


class SqlAlchemySubstitutionRepository(AbstractSubstitutionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_first_per_team(self, match_id: int) -> int:
        # El equipo se identifica por el usuario del integrante que sale: el
        # trigger garantiza que el que entra es del mismo equipo.
        first_ids = list(
            self.db.scalars(
                select(func.min(Substitution.id))
                .join(TeamMember, TeamMember.id == Substitution.member_out_id)
                .where(Substitution.match_id == match_id)
                .group_by(TeamMember.user_id)
            )
        )
        if not first_ids:
            return 0
        self.db.execute(delete(Substitution).where(Substitution.id.in_(first_ids)))
        self.db.commit()
        return len(first_ids)