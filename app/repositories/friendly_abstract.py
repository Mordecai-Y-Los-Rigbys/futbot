from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class FriendlyClubData(BaseModel):
    id: int
    username: str
    club_name: str
    
        
class FriendlyMatchData(BaseModel):
    id: int
    name: str | None
    status: str
    club1: FriendlyClubData
    created_at: datetime
    club2: FriendlyClubData | None = None


class CreateFriendlyMemberData(BaseModel):
    player_id: int
    behavior_id: int
    role: str


class CreateFriendlyData(BaseModel):
    name: str
    creator_id: int
    members: list[CreateFriendlyMemberData]
    
    
class FriendlyJoinState(BaseModel):
    id: int
    creator_id: int
    rival_id: int | None
    status: str


class JoinFriendlyData(BaseModel):
    match_id: int
    user_id: int
    members: list[CreateFriendlyMemberData]
    
class FriendlyPageData(BaseModel):
    items: list[FriendlyMatchData]
    total: int


class AbstractFriendlyRepository(ABC):
    @abstractmethod
    def user_is_playing(self, user_id: int) -> bool:
        """True si el usuario participa de un partido `started`, o de un
        amistoso `scheduled` (esperando rival o por arrancar)."""

    @abstractmethod
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son jugadores del usuario."""

    @abstractmethod
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son behaviors del usuario."""

    @abstractmethod
    def create_with_team(self, data: CreateFriendlyData) -> FriendlyMatchData:
        """Crea el partido `scheduled` y el equipo del creador en una única
        transacción (o nada)."""

    @abstractmethod
    def list_waiting_page(
        self, exclude_user_id: int, name: str | None, offset: int, limit: int
    ) -> FriendlyPageData:
        """Amistosos esperando rival creados por otros usuarios, ordenados por
        id ascendente, con `total` calculado con los mismos filtros."""
        
    @abstractmethod
    def get_friendly_state(self, match_id: int) -> FriendlyJoinState | None:
        """Estado mínimo de un amistoso (partido sin liga), o None si no existe
        o es un partido de liga."""

    @abstractmethod
    def join_friendly(self, data: JoinFriendlyData) -> FriendlyMatchData | None:
        """Ocupa `club2` con una actualización condicional (solo si el partido
        sigue siendo un amistoso esperando rival y el usuario no es el creador)
        y guarda el equipo del rival, todo en una transacción. Devuelve None si
        el partido ya no admitía rival (sin escribir nada)."""
