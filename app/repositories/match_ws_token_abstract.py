from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class MatchWsTokenData(BaseModel):
    token: str
    user_id: int
    match_id: int
    expires_at: datetime

    model_config = {"from_attributes": True}


class AbstractMatchWsTokenRepository(ABC):
    @abstractmethod
    def get_by_token(self, token: str) -> MatchWsTokenData | None:
        pass