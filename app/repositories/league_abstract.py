from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel
from app.domain.league import LeagueStatus
from app.domain.league_participant_member import MemberRole


class LeagueCreatorData(BaseModel):
    id: int
    username: str
    club_name: str

    model_config = {"from_attributes": True}


class LeagueListItemData(BaseModel):
    id: int
    name: str
    creator: LeagueCreatorData
    status: LeagueStatus
    participants_count: int
    max_participants: int
    private: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaguePageData(BaseModel):
    items: list[LeagueListItemData]
    total: int


class CreateLeagueMemberData(BaseModel):
    player_id: int
    behavior_id: int
    role: MemberRole


class CreateLeagueData(BaseModel):
    name: str
    creator_id: int
    min_participants: int
    max_participants: int
    match_duration: int
    private: bool
    password: str | None  # None si la liga es pública
    members: list[CreateLeagueMemberData]


class AbstractLeagueRepository(ABC):
    @abstractmethod
    def list_page(
        self, name: str | None, offset: int, limit: int
    ) -> LeaguePageData:
        """
        Devuelve una página de ligas ordenadas por id ascendente, con el
        creador y la cantidad de participantes (incluido el creador).
        Si `name` viene, filtra por coincidencia parcial case-insensitive
        tratando %, _ y \\ de forma literal. `total` es la cantidad de
        ligas que matchean el filtro, sin offset/limit.
        """
        pass

    @abstractmethod
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son jugadores del usuario."""
        pass

    @abstractmethod
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]:
        """Subconjunto de `ids` que son behaviors del usuario."""
        pass

    @abstractmethod
    def create(self, data: CreateLeagueData) -> LeagueListItemData:
        """
        Crea la liga en estado `preparation`, inscribe al creador y guarda su
        equipo, todo en una única transacción (o nada).
        """
        pass