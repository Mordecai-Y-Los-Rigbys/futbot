from pydantic import BaseModel


class FirstSubstitutionData(BaseModel):
    user_id: int  # equipo: usuario del integrante que sale
    starter_name: str
    substitute_name: str

from abc import ABC, abstractmethod


class AbstractSubstitutionRepository(ABC):
    @abstractmethod
    def list_first_per_team(self, match_id: int) -> list[FirstSubstitutionData]:
        """La sustitución más antigua (menor id) de cada equipo en el partido.
        Un equipo sin sustituciones no aparece."""