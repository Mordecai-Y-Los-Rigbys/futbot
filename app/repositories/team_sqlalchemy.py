from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.behavior import BehaviorType
from app.models.behavior import Behavior
from app.models.league_participant import LeagueParticipant
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.repositories.team_abstract import (
    AbstractTeamRepository,
    LineupPlayerData,
    MatchTeamData,
    StarterData,
    TeamBehaviorData,
    TeamMemberData,
)

# Titulares en este orden, después los suplentes (orden del contrato).
_ROLE_ORDER = {
    MemberRole.forward: 0,
    MemberRole.midfield: 1,
    MemberRole.defense: 2,
    MemberRole.substitute: 3,
}


def _team_owner(match_id: int, league_id: int | None):
    # El equipo de un partido de liga es el de la liga; el de un amistoso, el del partido.
    if league_id is None:
        return TeamMember.match_id == match_id
    return TeamMember.league_id == league_id


class SqlAlchemyTeamRepository(AbstractTeamRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_member_id(
        self,
        match_id: int,
        league_id: int | None,
        user_id: int,
        player_id: int,
        *,
        substitute: bool,
    ) -> int | None:
        role_filter = (
            TeamMember.role == MemberRole.substitute
            if substitute
            else TeamMember.role != MemberRole.substitute
        )
        return self.db.scalar(
            select(TeamMember.id).where(
                _team_owner(match_id, league_id),
                TeamMember.user_id == user_id,
                TeamMember.player_id == player_id,
                role_filter,
            )
        )

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

    def get_lineup(
        self, match_id: int, league_id: int | None, user_id: int
    ) -> list[LineupPlayerData]:
        rows = self.db.execute(
            select(Player.id, Player.name, TeamMember.role)
            .join(Player, Player.id == TeamMember.player_id)
            .where(
                _team_owner(match_id, league_id),
                TeamMember.user_id == user_id,
                TeamMember.role != MemberRole.substitute,
            )
        ).all()

        return [
            LineupPlayerData(player_id=player_id, name=name, role=role)
            for player_id, name, role in rows
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

    def get_match_team(self, match_id: int, league_id: int | None, user_id: int) -> MatchTeamData:
        rows = self.db.execute(
            select(
                TeamMember.id.label("member_id"),
                TeamMember.player_id.label("player_id"),
                Player.name.label("player_name"),
                TeamMember.role.label("role"),
                Behavior.id.label("behavior_id"),
                Behavior.name.label("behavior_name"),
                Behavior.type.label("behavior_type"),
            )
            .join(Player, Player.id == TeamMember.player_id)
            .join(Behavior, Behavior.id == TeamMember.behavior_id)
            .where(_team_owner(match_id, league_id), TeamMember.user_id == user_id)
        ).all()

        # Orden en Python (no en SQL): titulares por rol, suplentes por id de fila.
        rows = sorted(rows, key=lambda row: (_ROLE_ORDER[MemberRole(row.role)], row.member_id))
        members = [
            TeamMemberData(
                player_id=row.player_id,
                name=row.player_name,
                role=MemberRole(row.role),
                behavior=TeamBehaviorData(
                    id=row.behavior_id,
                    name=row.behavior_name,
                    type=BehaviorType(row.behavior_type),
                ),
            )
            for row in rows
        ]
        return MatchTeamData(
            members=members, coach_behavior=self._coach_behavior(league_id, user_id)
        )

    def _coach_behavior(self, league_id: int | None, user_id: int) -> TeamBehaviorData | None:
        # El DT se guarda en la inscripción a la liga. Los amistosos todavía no
        # persisten `coachBehaviorId`: su equipo no tiene DT (None).
        if league_id is None:
            return None
        row = self.db.execute(
            select(
                Behavior.id.label("behavior_id"),
                Behavior.name.label("behavior_name"),
                Behavior.type.label("behavior_type"),
            )
            .join(LeagueParticipant, LeagueParticipant.coach_behavior_id == Behavior.id)
            .where(
                LeagueParticipant.league_id == league_id,
                LeagueParticipant.user_id == user_id,
            )
        ).first()
        if row is None:
            return None
        return TeamBehaviorData(
            id=row.behavior_id, name=row.behavior_name, type=BehaviorType(row.behavior_type)
        )
