"""Ejecución de los comportamientos de todos los titulares en un tick."""

import logging
import time
from collections.abc import Callable, Mapping

from app.simulation import constants as C
from app.simulation.actions import PlayerActions
from app.simulation.behaviors.primitives import (
    ActionRecorder,
    MatchClock,
    behavior_constants,
    build_primitives,
)
from app.simulation.behaviors.sandbox import CompiledBehavior, run_behavior
from app.simulation.state import MatchState, PlayerKey, Team

logger = logging.getLogger(__name__)


class MissingBehaviorError(Exception):
    """Un titular no tiene comportamiento asignado."""


def run_behaviors(
    state: MatchState,
    behaviors: Mapping[PlayerKey, CompiledBehavior],
    clock: MatchClock,
    team_budget: float = C.TEAM_TIME_BUDGET,
    timer: Callable[[], float] = time.perf_counter,
) -> dict[PlayerKey, PlayerActions]:
    """Ejecuta el comportamiento de cada jugador y devuelve sus acciones en
    coordenadas absolutas.

    Cada equipo tiene `team_budget` segundos por tick para sus tres behaviors:
    cada jugador puede usar lo que sus compañeros anteriores no gastaron.
    """
    missing = [p.key for p in state.players if p.key not in behaviors]
    if missing:
        raise MissingBehaviorError(f"jugadores sin comportamiento: {missing}")

    constants = behavior_constants()
    actions: dict[PlayerKey, PlayerActions] = {}

    for team in (Team.HOME, Team.AWAY):
        remaining = team_budget
        for player in state.players:
            if player.team is not team:
                continue

            if remaining <= 0:
                # El equipo ya gastó su presupuesto en este tick: el jugador
                # no se ejecuta y sigue con su último movimiento.
                logger.warning(
                    "Sin tiempo para el comportamiento de %s en el tick %s", player.key, state.tick
                )
                actions[player.key] = PlayerActions()
                continue

            started = timer()
            actions[player.key] = _run_player(
                state, player.key, behaviors[player.key], clock, constants, remaining, timer
            )
            remaining -= timer() - started

    return actions


def _run_player(state, key, behavior, clock, constants, time_limit, timer) -> PlayerActions:
    recorder = ActionRecorder()
    # Namespace nuevo en cada tick: las variables no se conservan entre ticks.
    namespace = {**constants, **build_primitives(state, key, clock, recorder)}
    try:
        run_behavior(behavior, namespace, time_limit, timer)
    except Exception as error:
        # Se descarta lo pedido en este tick. PlayerActions() vacío hace que
        # el jugador siga con su último movimiento y no patee.
        logger.warning("Falló el comportamiento de %s en el tick %s: %r", key, state.tick, error)
        return PlayerActions()
    return recorder.actions()
