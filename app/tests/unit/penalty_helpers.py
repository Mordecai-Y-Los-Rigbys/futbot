"""Partido de prueba para los tests de la tanda de penales.

Los comportamientos son de una línea, para saber qué pasa en cada penal:
SCORE patea al arco rival por al lado del defensor, OWN lleva la pelota al
arco propio e IDLE no hace nada (el penal se agota). Durante el partido
nadie va a buscar la pelota, así que termina 0 a 0.
"""

from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.constants import STARTER_ROLES
from app.simulation.match_rules import MatchSession, TeamSetup, behaviors_by_key
from app.simulation.physics import PlayerSetup, create_initial_state
from app.simulation.state import Stats

SCORE = "if i_have_ball():\n    kick_to(field_length, 23)\n"
OWN = "go_to(0, field_width / 2)\n"
IDLE = "pass\n"

STATS = Stats(power=60, agility=60, control=60, strength=60, speed=60)
DURATION = 1  # segundo de juego: 20 ticks, sin cuenta regresiva ni pausas


def team(code: str, first_id: int) -> TeamSetup:
    return TeamSetup(
        players=[
            PlayerSetup(first_id + role.number, role, STATS, f"J{first_id + role.number}")
            for role in STARTER_ROLES
        ],
        behaviors={role: compile_behavior(code) for role in STARTER_ROLES},
    )


def play(code_1=IDLE, code_2=IDLE, allow_draws=False, seed=1, ball=None, periods=1) -> list:
    """Juega un partido completo. Los jugadores de club1 son 1-3 y los de club2, 11-13."""
    team_1, team_2 = team(code_1, 0), team(code_2, 10)
    state = create_initial_state(team_1.players, team_2.players, seed)
    if ball is not None:
        state.ball = ball
    session = MatchSession(
        state,
        behaviors_by_key(team_1, team_2),
        DURATION,
        countdown_seconds=0,
        periods=periods,
        pause_seconds=0,
        allow_draws=allow_draws,
    )
    ticks = []
    while not session.finished:
        ticks.append(session.advance())
    return ticks
