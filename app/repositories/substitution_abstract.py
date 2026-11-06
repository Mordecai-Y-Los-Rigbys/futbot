from abc import ABC, abstractmethod

from pydantic import BaseModel


class SubstitutionData(BaseModel):
    user_id: int  # equipo que pidió el cambio
    starter_name: str
    substitute_name: str


class AbstractSubstitutionRepository(ABC):
    @abstractmethod
    def list_by_match(self, match_id: int) -> list[SubstitutionData]:
        """La sustitución pedida de cada equipo en el partido (a lo sumo una
        por equipo). Un equipo sin sustitución no aparece."""

    @abstractmethod
    def delete_by_match(self, match_id: int) -> int:
        """Al terminar una pausa: borra las sustituciones de este partido
        (ya se aplicaron). Devuelve cuántas borró."""

    @abstractmethod
    def upsert(
        self, match_id: int, user_id: int, member_in_id: int, member_out_id: int
    ) -> None:
        """Reemplaza la única sustitución pendiente de este equipo."""
