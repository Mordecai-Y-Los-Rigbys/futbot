from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class SessionData(BaseModel):
    id: str
    user_id: int
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class CreateSessionData(BaseModel):
    id: str
    user_id: int
    created_at: datetime
    expires_at: datetime


class AbstractSessionRepository(ABC):
    @abstractmethod
    def create(self, session: CreateSessionData) -> SessionData:
        pass

    @abstractmethod
    def get_by_id(self, session_id: str) -> SessionData | None:
        pass

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Elimina la sesión. No falla si no existe."""
        pass