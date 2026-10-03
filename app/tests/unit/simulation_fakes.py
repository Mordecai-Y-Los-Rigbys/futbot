"""Equipos de prueba para los tests de simulación (sin base de datos)."""
from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.constants import STARTER_ROLES, CHASE_AND_SHOOT
from app.simulation.match_rules import TeamSetup
from app.simulation.physics import PlayerSetup
from app.simulation.state import Stats


def make_team(first_id: int = 0, stats: Stats | None = None) -> TeamSetup:
    """Tres titulares con el mismo behavior y stats parejos.

    Los ids de jugador son `first_id + role.number`. Dos equipos hechos con
    los mismos stats juegan en espejo hasta el primer desempate.
    """
    stats = stats or Stats(power=60, agility=60, control=60, strength=60, speed=60)
    behavior = compile_behavior(CHASE_AND_SHOOT)
    return TeamSetup(
        players=[PlayerSetup(first_id + r.number, r, stats) for r in STARTER_ROLES],
        behaviors={r: behavior for r in STARTER_ROLES},
    )