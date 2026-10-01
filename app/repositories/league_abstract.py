from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class LeagueCreatorData(BaseModel):
    id: int
    username: str
    club_name: str

    model_config = {"from_attributes": True}


class LeagueListItemData(BaseModel):
    id: int
    name: str
    creator: LeagueCreatorData
    status: str
    participants_count: int
    max_participants: int
    private: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaguePageData(BaseModel):
    items: list[LeagueListItemData]
    total: int


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