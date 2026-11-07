from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.behavior import BehaviorType
from app.models.behavior import Behavior
from app.models.league_participant import LeagueParticipant
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.repositories.team_abstract import (
    AbstractTeamRepository,
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

    def get_match_team(
        self, match_id: int, league_id: int | None, user_id: int
    ) -> MatchTeamData:
        # El equipo de un partido de liga es el de la liga; el de un amistoso, el del partido.
        owner = (
            TeamMember.match_id == match_id
            if league_id is None
            else TeamMember.league_id == league_id
        )
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
            .where(owner, TeamMember.user_id == user_id)
        ).all()

        # Orden en Python (no en SQL): titulares por rol, suplentes por id de fila.
        rows = sorted(rows, key=lambda r: (_ROLE_ORDER[MemberRole(r.role)], r.member_id))
        members = [
            TeamMemberData(
                player_id=r.player_id,
                name=r.player_name,
                role=MemberRole(r.role),
                behavior=TeamBehaviorData(
                    id=r.behavior_id,
                    name=r.behavior_name,
                    type=BehaviorType(r.behavior_type),
                ),
            )
            for r in rows
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