from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.repositories.team_abstract import AbstractTeamRepository, StarterData


class SqlAlchemyTeamRepository(AbstractTeamRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_team_player_ids(
        self, match_id: int, league_id: int | None, user_id: int, *, substitutes: bool
    ) -> set[int]:
        owner = (
            TeamMember.match_id == match_id
            if league_id is None
            else TeamMember.league_id == league_id
        )
        role_filter = (
            TeamMember.role == MemberRole.substitute
            if substitutes
            else TeamMember.role != MemberRole.substitute
        )
        rows = self.db.scalars(
            select(TeamMember.player_id).where(
                owner, TeamMember.user_id == user_id, role_filter
            )
        ).all()
        return set(rows)

    def get_member_id(
        self, match_id: int, league_id: int | None, user_id: int, player_id: int
    ) -> int | None:
        owner = (
            TeamMember.match_id == match_id
            if league_id is None
            else TeamMember.league_id == league_id
        )
        return self.db.scalar(
            select(TeamMember.id).where(
                owner,
                TeamMember.user_id == user_id,
                TeamMember.player_id == player_id,
            )
        )

    def get_starters(self, match_id: int, league_id: int | None, user_id: int) -> list[StarterData]:
        # El equipo de un partido de liga es el de la liga; el de un amistoso, el del partido.
        owner = (
            TeamMember.match_id == match_id
            if league_id is None
            else TeamMember.league_id == league_id
        )

        rows = self.db.execute(
            select(TeamMember.role, Player, Behavior.code)
            .join(Player, Player.id == TeamMember.player_id)
            .join(Behavior, Behavior.id == TeamMember.behavior_id)
            .where(
                owner,
                TeamMember.user_id == user_id,
                TeamMember.role != MemberRole.substitute,
            )
        ).all()

        return [
            StarterData(
                player_id=player.id,
                role=role,
                power=player.power,
                agility=player.agility,
                control=player.control,
                strength=player.strength,
                speed=player.speed,
                behavior_code=behavior_code,
            )
            for role, player, behavior_code in rows
        ]
