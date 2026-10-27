from abc import ABC, abstractmethod


class AbstractSubstitutionRepository(ABC):
    @abstractmethod
    def delete_first_per_team(self, match_id: int) -> int:
        """Al terminar una pausa: borra el cambio más antiguo de cada equipo
        en este partido. Devuelve cuántos borró."""