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
    def list_by_match(self, match_id: int, applied: bool) -> list[SubstitutionData]:
        """La sustitución de cada equipo en el partido, a lo sumo una por equipo:
        la aplicada en la pausa en curso (`applied=True`) o la pendiente para
        la próxima pausa (`applied=False`). Un equipo sin sustitución de ese
        tipo no aparece."""

    @abstractmethod
    def apply_by_match(self, match_id: int) -> list[AppliedSubstitution]:
        """Al empezar una pausa: aplica la sustitución pendiente de cada equipo,
        o sea intercambia los roles del que sale y del que entra (cada uno
        conserva su behavior) y la marca como aplicada. La fila aplicada sigue
        en `substitutions` hasta que termine la pausa, así que un GET todavía
        la muestra.

        Antes de aplicar toma el lock del partido (serializa con los PUT) y
        borra las aplicadas que hayan quedado de una pausa anterior.

        Devuelve lo que necesita el motor para poner al suplente en cancha.
        Es idempotente: una sustitución ya aplicada no se vuelve a aplicar.
        """

    @abstractmethod
    def delete_applied_by_match(self, match_id: int) -> int:
        """Al terminar una pausa: borra las sustituciones aplicadas de este
        partido. Las pendientes (pedidas durante la pausa) se conservan.
        Devuelve cuántas borró."""

    @abstractmethod
    def upsert(
        self, match_id: int, user_id: int, member_in_id: int, member_out_id: int
    ) -> None:
        """Reemplaza la única sustitución pendiente de este equipo. No toca la
        aplicada. Si los integrantes ya no corresponden a una pendiente
        (cambió la alineación), propaga IntegrityError."""