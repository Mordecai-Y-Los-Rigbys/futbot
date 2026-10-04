from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class MatchAccessData(BaseModel):
    id: int
    status: str
    league_id: int | None = None
    league_creator_id: int | None = None
    league_private: bool = False
    league_password: str | None = None


class CreateMatchWsTokenData(BaseModel):
    token: str
    user_id: int
    match_id: int
    created_at: datetime
    expires_at: datetime


class AbstractMatchConnectionRepository(ABC):
    @abstractmethod
    def get_access(self, match_id: int) -> MatchAccessData | None:
        """Estado del partido y, si es de liga, datos de acceso de la liga.
        None si no existe."""

    @abstractmethod
    def is_league_participant(self, league_id: int, user_id: int) -> bool:
        """True si el usuario está inscripto en la liga (el creador incluido)."""

    @abstractmethod
    def create_token(self, data: CreateMatchWsTokenData) -> None:
        """Persiste el tokenWs."""