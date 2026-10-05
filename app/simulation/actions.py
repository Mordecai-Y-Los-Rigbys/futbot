"""Acciones que un jugador puede pedir en un tick (en coordenadas absolutas).

Las arma la ejecución de comportamientos a partir de las primitivas que llama
el código del usuario; el motor solo las resuelve aplicando la física.
"""

from dataclasses import dataclass

from app.simulation.constants import MAX_KICK_FORCE


@dataclass(frozen=True)
class MoveInDirection:
    """Moverse en la dirección (dx, dy). Solo importa la dirección, no el
    tamaño; (0, 0) es quedarse quieto."""

    dx: float
    dy: float


@dataclass(frozen=True)
class GoTo:
    """Ir hasta (x, y) y detenerse al llegar."""

    x: float
    y: float


@dataclass(frozen=True)
class Kick:
    """Patear hacia adelante, en la línea jugador -> pelota."""

    force: int = MAX_KICK_FORCE


@dataclass(frozen=True)
class KickTo:
    """Patear hacia (x, y)."""

    x: float
    y: float
    force: int = MAX_KICK_FORCE


MoveAction = MoveInDirection | GoTo
KickAction = Kick | KickTo


@dataclass(frozen=True)
class PlayerActions:
    """Lo que pide un jugador en un tick: a lo sumo un movimiento y una patada.
    `move=None` mantiene el último movimiento pedido."""

    move: MoveAction | None = None
    kick: KickAction | None = None
