from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.repositories.team_abstract import AbstractTeamRepository, StarterData


def _team_owner(match_id: int, league_id: int | None):
    # El equipo de un partido de liga es el de la liga; el de un amistoso, el del partido.
    if league_id is None:
        return TeamMember.match_id == match_id
    return TeamMember.league_id == league_id


class SqlAlchemyTeamRepository(AbstractTeamRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_starters(self, match_id: int, league_id: int | None, user_id: int) -> list[StarterData]:
        rows = self.db.execute(
            select(TeamMember.role, Player, Behavior.code)
            .join(Player, Player.id == TeamMember.player_id)
            .join(Behavior, Behavior.id == TeamMember.behavior_id)
            .where(
                _team_owner(match_id, league_id),
                TeamMember.user_id == user_id,
                TeamMember.role != MemberRole.substitute,
            )
        ).all()

        return [
            StarterData(
                player_id=player.id,
                name=player.name,
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

    def set_behavior(
        self, match_id: int, league_id: int | None, player_id: int, behavior_id: int
    ) -> None:
        self.db.execute(
            update(TeamMember)
            .where(_team_owner(match_id, league_id), TeamMember.player_id == player_id)
            .values(behavior_id=behavior_id)
        )
        self.db.commit()
