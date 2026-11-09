from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

from app.repositories.team_abstract import StarterData


class SubstitutionData(BaseModel):
    user_id: int  # equipo que pidió el cambio
    starter_name: str
    substitute_name: str


class AppliedSwap(BaseModel):
    """Un cambio que acaba de aplicarse: lo que el motor necesita para ponerlo en cancha."""

    club: Literal["club1", "club2"]
    out_player_id: int  # el titular que sale
    incoming: StarterData  # el suplente que entra, ya con el rol del que salió


class AbstractSubstitutionRepository(ABC):
    @abstractmethod
    def list_by_match(self, match_id: int) -> list[SubstitutionData]:
        """La sustitución PENDIENTE de cada equipo en el partido (a lo sumo una
        por equipo). Un equipo sin sustitución pendiente no aparece."""

    @abstractmethod
    def list_applied_by_match(self, match_id: int) -> list[SubstitutionData]:
        """La sustitución APLICADA al empezar la última pausa (a lo sumo una por
        equipo). Un equipo al que no se le aplicó ninguna no aparece."""

    @abstractmethod
    def apply_pending(self, match_id: int) -> list[AppliedSwap]:
        """Al empezar una pausa, en una sola transacción:

        - descarta las aplicadas de la pausa anterior;
        - aplica la pendiente de cada equipo: el suplente toma el rol del
          titular y el titular pasa a suplente (en `team_members`);
        - guarda lo aplicado y borra las pendientes.

        Una pendiente que ya no es válida (el que sale ya no es titular o el que
        entra ya no es suplente) se descarta sin aplicarse. Devuelve lo aplicado."""

    @abstractmethod
    def upsert(
        self, match_id: int, user_id: int, member_in_id: int, member_out_id: int
    ) -> None:
        """Reemplaza la única sustitución pendiente de este equipo. Si los
        integrantes ya no corresponden a una pendiente (cambió la alineación),
        propaga IntegrityError."""
