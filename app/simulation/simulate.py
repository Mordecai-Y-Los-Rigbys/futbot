"""Simulador sin tiempo real: mismo partido, sin esperar entre ticks."""

from dataclasses import dataclass

from app.simulation.constants import COUNTDOWN_SECONDS
from app.simulation.match_rules import TeamSetup, TickResult, build_session

@dataclass(frozen=True)
class SimulationResult:
    score_1: int
    score_2: int
    ticks: list[TickResult]


def simulate_match(
    team_1: TeamSetup,
    team_2: TeamSetup,
    duration_seconds: float,
    seed: int,
    countdown_seconds: float = COUNTDOWN_SECONDS,
) -> SimulationResult:
    """Corre el partido completo. `duration_seconds` es el tiempo de juego,
    sin contar la cuenta regresiva. Misma semilla y mismos equipos => mismos ticks."""
    session = build_session(team_1, team_2, duration_seconds, seed, countdown_seconds)
    ticks: list[TickResult] = []
    while not session.finished:
        ticks.append(session.advance())
    last = ticks[-1]
    return SimulationResult(last.score_1, last.score_2, ticks)