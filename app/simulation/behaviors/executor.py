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
from app.simulation.state import MatchState, PlayerKey

logger = logging.getLogger(__name__)


class MissingBehaviorError(Exception):
    """Un titular no tiene comportamiento asignado."""


def run_behaviors(
    state: MatchState,
    behaviors: Mapping[PlayerKey, CompiledBehavior],
    clock: MatchClock,
    time_limit: float = C.BEHAVIOR_TIME_LIMIT,
    timer: Callable[[], float] = time.perf_counter,
) -> dict[PlayerKey, PlayerActions]:
    """Ejecuta el comportamiento de cada jugador y devuelve sus acciones en
    coordenadas absolutas.
    """
    missing = [p.key for p in state.players if p.key not in behaviors]
    if missing:
        raise MissingBehaviorError(f"jugadores sin comportamiento: {missing}")

    constants = behavior_constants()
    return {
        player.key: _run_player(
            state, player.key, behaviors[player.key], clock, constants, time_limit, timer
        )
        for player in state.players
    }


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
