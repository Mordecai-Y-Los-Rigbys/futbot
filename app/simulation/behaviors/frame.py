"""Traducción entre coordenadas absolutas (motor) y relativas a un equipo
(comportamientos).

Para el local, las dos coinciden. Para el visitante, la cancha se ve rotada
180°: su arco queda en x = 0 y el rival en x = FIELD_LENGTH, igual que para el
local. Así, el mismo comportamiento funciona igual en los dos equipos.

La rotación es su propia inversa: la misma cuenta sirve para ir y volver.
"""

from app.simulation import constants as C
from app.simulation.geometry import Vec
from app.simulation.state import Team


def to_relative(team: Team, point: Vec) -> tuple[float, float]:
    """Punto absoluto del motor -> (x, y) como lo ve el comportamiento."""
    if team is Team.HOME:
        return (point.x, point.y)
    return (C.FIELD_LENGTH - point.x, C.FIELD_WIDTH - point.y)


def to_absolute(team: Team, x: float, y: float) -> Vec:
    """(x, y) pedido por el comportamiento -> punto absoluto del motor."""
    if team is Team.HOME:
        return Vec(x, y)
    return Vec(C.FIELD_LENGTH - x, C.FIELD_WIDTH - y)


def direction_to_absolute(team: Team, dx: float, dy: float) -> tuple[float, float]:
    """Dirección pedida por el comportamiento -> dirección absoluta del motor.

    Las direcciones no dependen del origen: para el visitante solo se invierten.
    """
    if team is Team.HOME:
        return (dx, dy)
    return (-dx, -dy)
