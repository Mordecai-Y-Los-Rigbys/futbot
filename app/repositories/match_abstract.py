from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel

from app.domain.match import MatchStatus
from app.repositories.friendly_abstract import FriendlyClubData
from app.repositories.league_access_abstract import LeagueAccessInfo


class MatchStateData(BaseModel):
    id: int
    status: MatchStatus


class MatchSetupData(BaseModel):
    id: int
    league_id: int | None
    user_1_id: int
    user_2_id: int | None
    club_1_name: str
    club_2_name: str | None
    allow_draws: bool


class PenaltyShootoutData(BaseModel):
    score_1: int
    score_2: int
    winner: int  # 1 si es club1, 2 si club2
    kicks: list[dict]


class MatchPlayersData(BaseModel):
    id: int
    status: MatchStatus
    user_1_id: int
    user_2_id: int | None
    league_id: int | None


class MatchDetailData(BaseModel):
    id: int
    league_id: int | None
    name: str | None
    status: MatchStatus
    club1: FriendlyClubData
    club2: FriendlyClubData | None
    scheduled_at: datetime | None
    created_at: datetime
    score_1: int | None
    score_2: int | None
    league: LeagueAccessInfo | None  # None en los amistosos
    penalties: PenaltyShootoutData | None = None  # None si no hubo tanda


class AbstractMatchRepository(ABC):
    @abstractmethod
    def get_state(self, match_id: int) -> MatchStateData | None:
        """Devuelve el estado mínimo del partido, o None si no existe."""

    @abstractmethod
    def get_setup_data(self, match_id: int) -> MatchSetupData | None:
        """Datos del partido y nombres de los clubes, o None si no existe."""

    @abstractmethod
    def get_detail(self, match_id: int) -> MatchDetailData | None:
        """Partido con sus dos clubes, su resultado y, si es de liga, los datos
        de acceso de la liga. None si no existe."""

    @abstractmethod
    def mark_started(self, match_id: int) -> None:
        """Pasa el partido de scheduled a started."""

    @abstractmethod
    def finish(
        self,
        match_id: int,
        score_1: int,
        score_2: int,
        penalties: PenaltyShootoutData | None = None,
    ) -> bool:
        """Guarda el resultado, y la tanda si la hubo, y pasa el partido a finished.

        Si era el último partido sin terminar de una liga en curso, pasa la
        liga a finished en la misma transacción. Devuelve True solo en ese caso.
        """

    @abstractmethod
    def save_seed(self, match_id: int, seed: int) -> None:
        """Guarda la semilla con la que se juega el partido (para reproducirlo)."""

    @abstractmethod
    def get_players(self, match_id: int) -> MatchPlayersData | None:
        """Estado, liga y usuarios del partido, o None si no existe."""
