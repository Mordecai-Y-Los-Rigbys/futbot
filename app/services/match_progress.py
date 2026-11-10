"""En qué punto está un partido que se juega en este proceso.

Lo escribe el MatchRunner en cada tick y lo lee la API (por ejemplo, para saber
si un partido está en pausa o ya no le quedan pausas).
"""

from dataclasses import dataclass
from typing import Protocol

from app.simulation.match_rules import Phase


@dataclass(frozen=True)
class MatchProgress:
    phase: Phase
    period: int  # en un countdown, el que arranca; en una pausa, el que terminó
    periods: int  # cantidad total de períodos (pausas = periods - 1)


class MatchProgressReader(Protocol):
    """Lo que la API necesita del runner (lo cumple MatchRunner)."""

    def progress(self, match_id: int) -> MatchProgress | None:
        """None si el partido no se está jugando en este proceso."""

