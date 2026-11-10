from typing import Literal

from pydantic import BaseModel

from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole
from app.schemas.base import CamelModel


class TeamBehavior(CamelModel):
    """`BehaviorSummary` del contrato (id, name, type). El código no viaja acá:
    se pide con GET /matches/{id}/behavior?playerId=..."""

    id: int
    name: str
    type: BehaviorType


class MatchTeamMember(CamelModel):
    player_id: int
    name: str
    role: MemberRole
    behavior: TeamBehavior


class MatchTeam(CamelModel):
    """Respuesta de GET /matches/{id}/team: siempre 6 miembros (3 titulares y
    después 3 suplentes) y el behavior del DT, o `null` si el equipo no tiene."""

    members: list[MatchTeamMember]
    coach_behavior: TeamBehavior | None


class MatchTeamForbidden(BaseModel):
    code: Literal["notAPlayerInMatch"]
    message: str
