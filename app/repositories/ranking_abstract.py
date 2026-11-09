from abc import ABC, abstractmethod

from pydantic import BaseModel


class ClubRankingData(BaseModel):
    """Totales de un club sobre sus partidos finalizados de ligas públicas."""

    club_id: int
    name: str
    avatar: int
    won_regular: int  # ganados sin penales
    won_penalties: int  # ganados por penales
    drawn: int
    lost: int  # incluye perdidos por penales
    goals_for: int  # solo goles del juego, sin tanda
    goals_against: int


class AbstractRankingRepository(ABC):
    @abstractmethod
    def list_club_totals(self) -> list[ClubRankingData]:
        """Un elemento por club con al menos un partido finalizado de una liga
        pública que ya no está en `preparation`. Sin orden garantizado."""
