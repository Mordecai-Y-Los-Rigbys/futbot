from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.repositories.team_abstract import StarterData


class SubstitutionData(BaseModel):
    user_id: int  # equipo que pidió el cambio
    starter_name: str
    substitute_name: str


class AppliedSubstitution(BaseModel):
    user_id: int  # equipo que hizo el cambio
    incoming: StarterData  # el que entró: con el rol del titular que salió


class AbstractSubstitutionRepository(ABC):
    @abstractmethod
    def list_by_match(self, match_id: int) -> list[SubstitutionData]:
        """La sustitución pedida de cada equipo en el partido (a lo sumo una
        por equipo). Un equipo sin sustitución no aparece."""

    @abstractmethod
    def apply_by_match(self, match_id: int) -> list[AppliedSubstitution]:
        """Al empezar una pausa: aplica la sustitución de cada equipo, o sea
        intercambia los roles del que sale y del que entra en el equipo
        (cada uno conserva su behavior). La fila sigue en `substitutions`
        hasta que termine la pausa, así que un GET todavía la muestra.

        Devuelve lo que necesita el motor para poner al suplente en cancha.
        Es idempotente: una sustitución ya aplicada no se vuelve a aplicar.
        """

    @abstractmethod
    def delete_by_match(self, match_id: int) -> int:
        """Al terminar una pausa: borra las sustituciones de este partido
        (ya se aplicaron al empezarla). Devuelve cuántas borró."""

    @abstractmethod
    def upsert(
        self, match_id: int, user_id: int, member_in_id: int, member_out_id: int
    ) -> None:
        """Reemplaza la única sustitución pendiente de este equipo."""
