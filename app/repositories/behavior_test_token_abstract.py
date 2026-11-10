from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.team_member import MemberRole


class BehaviorTestMemberData(BaseModel):
    player_id: int
    club: Literal["club1", "club2"]
    role: MemberRole
    behavior_id: int


class BehaviorTestTokenData(BaseModel):
    token: str
    user_id: int
    behavior_id: int
    expires_at: datetime
    members: list[BehaviorTestMemberData]


class CreateBehaviorTestTokenData(BaseModel):
    token: str
    user_id: int
    behavior_id: int
    created_at: datetime
    expires_at: datetime
    members: list[BehaviorTestMemberData]


class AbstractBehaviorTestTokenRepository(ABC):
    @abstractmethod
    def create(self, data: CreateBehaviorTestTokenData) -> None:
        """Guarda el token con su alineación y confirma la transacción."""

    @abstractmethod
    def get_by_token(self, token: str) -> BehaviorTestTokenData | None:
        """El token, o None si no existe. Lo usa el handshake de /ws/behaviors/{id}/test."""
