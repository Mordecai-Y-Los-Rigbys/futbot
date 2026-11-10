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
    # Pausas que no empezaron: el `pausesLeft` del tick. Es la única fuente de la
    # regla `noPausesLeft` (== 0): no se la recalcula desde los períodos.
    pauses_left: int


class MatchProgressReader(Protocol):
    """Lo que la API necesita del runner (lo cumple MatchRunner)."""

    def progress(self, match_id: int) -> MatchProgress | None:
        """None si el partido no se está jugando en este proceso."""
