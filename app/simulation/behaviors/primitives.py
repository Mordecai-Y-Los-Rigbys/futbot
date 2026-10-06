"""Primitivas y constantes que ve el código de un comportamiento.

Implementan docs/API Comportamientos.md. Todo lo que entra y sale está en
coordenadas relativas al equipo del jugador (ver frame.py). Las primitivas solo
leen el estado del partido: lo único que hacen es registrar en un
ActionRecorder el movimiento y la patada a la pelota pedidos, que después resuelve la
física.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.simulation import constants as C
from app.simulation.actions import GoTo, Kick, KickTo, MoveInDirection, PlayerActions
from app.simulation.behaviors.frame import direction_to_absolute, to_absolute, to_relative
from app.simulation.state import MatchState, PlayerKey, PlayerState, Team

STATS = ("power", "agility", "control", "strength", "speed")
PLAYER_NUMBERS = frozenset(role.number for role in C.STARTER_ROLES)


class BehaviorError(Exception):
    """Uso inválido de una primitiva. Corta la ejecución del comportamiento."""


@dataclass(frozen=True)
class MatchClock:
    """Tiempo de juego, que lleva el loop del partido."""

    elapsed: float  # segundos jugados
    remaining: float  # segundos que faltan
    period: int = 1  # mientras no haya períodos, siempre 1


class ActionRecorder:
    """Guarda lo que pide el comportamiento en un tick: a lo sumo un
    movimiento y una patada a la pelota. Si se pide más de uno del mismo tipo, vale el
    último."""

    def __init__(self) -> None:
        self.move: MoveInDirection | GoTo | None = None
        self.kick: Kick | KickTo | None = None

    def actions(self) -> PlayerActions:
        return PlayerActions(move=self.move, kick=self.kick)


def behavior_constants() -> dict[str, Any]:
    """Constantes de la API. Son iguales para los dos equipos porque están en
    coordenadas relativas."""
    length, width = C.FIELD_LENGTH, C.FIELD_WIDTH
    return {
        "field_length": length,
        "field_width": width,
        "goal_width": C.GOAL_WIDTH,
        "player_radius": C.PLAYER_RADIUS,
        "ball_radius": C.BALL_RADIUS,
        "my_goal": (0.0, width / 2),  # (0, 30)
        "opponent_goal": (length, width / 2),  # (100, 30)
        "field_center": (length / 2, width / 2),  # (50, 30)
        "bottom_left_corner": (0.0, 0.0),
        "bottom_right_corner": (length, 0.0),
        "top_left_corner": (0.0, width),
        "top_right_corner": (length, width),
    }


# --- validación de argumentos -------------------------------------------------


def _number(value: Any, name: str) -> float:
    # bool es subclase de int en Python, podrian mandar True como valor 1. Se rechazan inf y
    # NaN porque romperían la física.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BehaviorError(f"`{name}` tiene que ser un número")
    if not math.isfinite(value):
        raise BehaviorError(f"`{name}` tiene que ser un número finito")
    return float(value)


def _player_number(num: Any) -> int:
    if isinstance(num, bool) or not isinstance(num, int) or num not in PLAYER_NUMBERS:
        raise BehaviorError(f"el número de jugador tiene que estar entre 1 y 3, no {num!r}")
    return num


def _stat_name(stat: Any) -> str:
    if stat not in STATS:
        raise BehaviorError(f"`{stat!r}` no es una stat: {', '.join(STATS)}")
    return stat


# --- primitivas ---------------------------------------------------------------


def build_primitives(
    state: MatchState, key: PlayerKey, clock: MatchClock, recorder: ActionRecorder
) -> dict[str, Callable[..., Any]]:
    """Primitivas para el jugador `key`, atadas al estado de este tick."""
    me = state.player(key)
    team = me.team
    ball = state.ball

    def player(of_team: Team, num: Any) -> PlayerState:
        return state.player((of_team, _player_number(num)))

    # Movimiento
    def move_in_direction(dir_x: Any, dir_y: Any) -> None:
        dx, dy = direction_to_absolute(team, _number(dir_x, "dir_x"), _number(dir_y, "dir_y"))
        recorder.move = MoveInDirection(dx, dy)

    def go_to(x: Any, y: Any) -> None:
        target = to_absolute(team, _number(x, "x"), _number(y, "y"))
        recorder.move = GoTo(target.x, target.y)

    # Patadas
    def kick(force: Any = C.MAX_KICK_FORCE) -> None:
        recorder.kick = Kick(force=_number(force, "force"))

    def kick_to(x: Any, y: Any, force: Any = C.MAX_KICK_FORCE) -> None:
        target = to_absolute(team, _number(x, "x"), _number(y, "y"))
        recorder.kick = KickTo(target.x, target.y, force=_number(force, "force"))

    # Información del propio jugador
    def my_position() -> tuple[float, float]:
        return to_relative(team, me.position)

    def my_number() -> int:
        return me.number

    def i_have_ball() -> bool:
        return ball.owner == key

    # Información de otros jugadores
    def teammate_position(num: Any) -> tuple[float, float]:
        return to_relative(team, player(team, num).position)

    def opponent_position(num: Any) -> tuple[float, float]:
        return to_relative(team, player(team.opponent, num).position)

    def teammate_stat(num: Any, stat: Any) -> int:
        return getattr(player(team, num).stats, _stat_name(stat))

    def opponent_stat(num: Any, stat: Any) -> int:
        return getattr(player(team.opponent, num).stats, _stat_name(stat))

    # Pelota.
    def ball_position() -> tuple[float, float]:
        return to_relative(team, ball.position)

    def teammate_has_ball() -> bool:
        return ball.owner is not None and ball.owner[0] is team and ball.owner != key

    def opponent_has_ball() -> bool:
        return ball.owner is not None and ball.owner[0] is team.opponent

    def nobody_has_ball() -> bool:
        return ball.owner is None

    # Utilidades
    def distance(x1: Any, y1: Any, x2: Any, y2: Any) -> float:
        return math.hypot(
            _number(x2, "x2") - _number(x1, "x1"), _number(y2, "y2") - _number(y1, "y1")
        )

    # Tiempo
    def elapsed_time() -> float:
        return clock.elapsed

    def remaining_time() -> float:
        return clock.remaining

    def current_period() -> int:
        return clock.period

    return {
        "move_in_direction": move_in_direction,
        "go_to": go_to,
        "kick": kick,
        "kick_to": kick_to,
        "my_position": my_position,
        "my_number": my_number,
        "i_have_ball": i_have_ball,
        "teammate_position": teammate_position,
        "opponent_position": opponent_position,
        "teammate_stat": teammate_stat,
        "opponent_stat": opponent_stat,
        "ball_position": ball_position,
        "teammate_has_ball": teammate_has_ball,
        "opponent_has_ball": opponent_has_ball,
        "nobody_has_ball": nobody_has_ball,
        "distance": distance,
        "elapsed_time": elapsed_time,
        "remaining_time": remaining_time,
        "current_period": current_period,
    }
