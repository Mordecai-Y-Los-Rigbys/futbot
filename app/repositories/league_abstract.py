from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

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


# Conflictos de inscripción que dependen del estado de la liga, en el orden
# en que se evalúan (enum de JoinLeagueConflict del contrato).
JoinLeagueStateConflict = Literal["notInPreparation", "leagueFull", "alreadyParticipating"]


class LeagueJoinState(BaseModel):
    """Lo que necesita POST /leagues/{id}/participants para decidir 403 y 409."""

    private: bool
    password: str | None
    status: LeagueStatus
    max_participants: int
    participants_count: int
    is_participant: bool  # el usuario que se inscribe ya participa

    def conflict(self) -> JoinLeagueStateConflict | None:
        """Primer 409 de estado que aplica, o None si la liga admite al usuario."""
        if self.status != LeagueStatus.preparation:
            return "notInPreparation"
        if self.participants_count >= self.max_participants:
            return "leagueFull"
        if self.is_participant:
            return "alreadyParticipating"
        return None


class JoinLeagueData(BaseModel):
    league_id: int
    user_id: int
    session_id: str
    members: list[CreateLeagueMemberData]
    coach_behavior_id: int | None  # None: el equipo no tiene DT
    unlock_session: bool  # True si la liga es privada: queda desbloqueada en la sesión


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
    def get_join_state(self, league_id: int, user_id: int) -> LeagueJoinState | None:
        """Estado de la liga visto por `user_id` que quiere inscribirse.

        Devuelve None si la liga no existe.
        """

    @abstractmethod
    def join(self, data: JoinLeagueData) -> JoinLeagueStateConflict | None:
        """Inscribe al usuario con su equipo y su DT, en una única transacción.

        Vuelve a evaluar estado, cupo y participación previa con la liga
        bloqueada, para que dos inscripciones simultáneas no superen el cupo.
        Si `unlock_session`, también registra el desbloqueo de la liga en la
        sesión dentro de la misma transacción.

        Returns:
            None si inscribió; el código del conflicto si, al bloquear la
            liga, ya no admitía al usuario (en ese caso no persiste nada).
        """
