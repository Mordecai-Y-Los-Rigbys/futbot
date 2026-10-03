"""Revisar un partido sin levantar el servidor.

    python -m app.simulation.run --seed 7 --duration 60
"""

import argparse

from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.constants import STARTER_ROLES, CHASE_AND_SHOOT, COUNTDOWN_SECONDS
from app.simulation.match_rules import Event, TeamSetup
from app.simulation.physics import PlayerSetup
from app.simulation.simulate import simulate_match
from app.simulation.state import Stats
from app.domain.team_member import MemberRole


def default_team(first_id: int) -> TeamSetup:
    behavior = compile_behavior(CHASE_AND_SHOOT)
    stats = Stats(power=60, agility=60, control=60, strength=60, speed=60)
    return TeamSetup(
        players=[PlayerSetup(first_id + r.number, r, stats) for r in STARTER_ROLES],
        behaviors={r: behavior for r in STARTER_ROLES},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula un partido de Futbot")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--duration", type=float, default=60, help="segundos de juego")
    parser.add_argument("--countdown", type=float, default=COUNTDOWN_SECONDS)
    args = parser.parse_args()

    result = simulate_match(
        default_team(0), default_team(10), args.duration, args.seed, args.countdown
    )
    for t in result.ticks:
        if t.event is Event.GOAL:
            print(f"gol en el tick {t.tick} ({t.elapsed:.2f}s): {t.score_1}-{t.score_2}")
    print(f"resultado: {result.score_1}-{result.score_2} en {len(result.ticks)} ticks")


if __name__ == "__main__":
    main()