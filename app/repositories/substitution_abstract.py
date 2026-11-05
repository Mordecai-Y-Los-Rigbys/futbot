# app/repositories/substitution_abstract.py
from abc import ABC, abstractmethod

from pydantic import BaseModel


class FirstSubstitutionData(BaseModel):
    user_id: int  # equipo: usuario del integrante que sale
    starter_name: str
    substitute_name: str


class AbstractSubstitutionRepository(ABC):
    @abstractmethod
    def list_first_per_team(self, match_id: int) -> list[FirstSubstitutionData]:
        """La sustitución más antigua (menor id) de cada equipo en el partido.
        Un equipo sin sustituciones no aparece."""

    @abstractmethod
    def delete_first_per_team(self, match_id: int) -> int:
        """Al terminar una pausa: borra el cambio más antiguo de cada equipo
        en este partido. Devuelve cuántos borró."""
