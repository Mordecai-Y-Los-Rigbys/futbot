from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class BehaviorTestTokenData(BaseModel):
    token: str
    user_id: int
    behavior_id: int
    expires_at: datetime


class CreateBehaviorTestTokenData(BaseModel):
    token: str
    user_id: int
    behavior_id: int
    created_at: datetime
    expires_at: datetime


class AbstractBehaviorTestTokenRepository(ABC):
    @abstractmethod
    def create(self, data: CreateBehaviorTestTokenData) -> None:
        """Guarda el token y confirma la transacción."""

    @abstractmethod
    def get_by_token(self, token: str) -> BehaviorTestTokenData | None:
        """El token, o None si no existe. Lo usa el handshake de /ws/behaviors/{id}/test."""