from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel
from app.domain.league import LeagueStatus
from app.domain.team_member import MemberRole


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
    

class LeagueLeaveInfo(BaseModel):
    status: LeagueStatus
    creator_id: int


class AbstractLeagueRepository(ABC):
    @abstractmethod
    def list_page(self, name: str | None, offset: int, limit: int) -> LeaguePageData:
        """
        Devuelve una página de ligas ordenadas por id ascendente, con el
        creador y la cantidad de participantes (incluido el creador).
        Si `name` viene, filtra por coincidencia parcial case-insensitive
        tratando %, _ y \\ de forma literal. `total` es la cantidad de
        ligas que matchean el filtro, sin offset/limit.
        """

    @abstractmethod
    def create(self, data: CreateLeagueData) -> LeagueListItemData:
        """
        Crea la liga en estado `preparation`, inscribe al creador y guarda su
        equipo, todo en una única transacción (o nada).
        """

    @abstractmethod
    def get_match_duration_minutes(self, league_id: int) -> int | None:
        """Duración de cada partido de la liga, en minutos.

        Es el valor `match_duration` que definió el creador al crear la liga
        (entre 1 y 10). Devuelve None si la liga no existe.
        """
    
    @abstractmethod
    def get_leave_info(self, league_id: int) -> LeagueLeaveInfo | None:
        """Estado y creador de la liga. Devuelve None si la liga no existe."""
    
    @abstractmethod
    def is_participant(self, league_id: int, user_id: int) -> bool:
        """True si el usuario está inscripto en la liga (el creador incluido)."""
    
    @abstractmethod
    def remove_participant(self, league_id: int, user_id: int) -> None:
        """
        Elimina la inscripción del usuario y el equipo que registró en esa liga,
        en una única transacción (o nada).
        """
