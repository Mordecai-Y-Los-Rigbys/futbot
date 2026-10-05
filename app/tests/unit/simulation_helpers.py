"""Helpers para armar estados de partido a mano en los tests de la física."""

from app.simulation.actions import PlayerActions
from app.simulation.geometry import Vec
from app.simulation.physics import step
from app.simulation.state import (
    BallState,
    MatchState,
    PlayerKey,
    PlayerState,
    Role,
    Stats,
    Team,
)

HOME, AWAY = Team.HOME, Team.AWAY
_ROLES = {1: Role.DEFENSE, 2: Role.MIDFIELD, 3: Role.FORWARD}


def stats(power=60, agility=60, control=60, strength=60, speed=60) -> Stats:
    return Stats(power=power, agility=agility, control=control, strength=strength, speed=speed)


def player(team=HOME, number=1, x=50.0, y=30.0, player_id=None, **stat_values) -> PlayerState:
    return PlayerState(
        player_id=player_id if player_id is not None else number + (10 if team is AWAY else 0),
        team=team,
        role=_ROLES[number],
        stats=stats(**stat_values),
        position=Vec(x, y),
        facing=Vec(1.0, 0.0) if team is HOME else Vec(-1.0, 0.0),
    )


def state(*players, ball=(80.0, 50.0), velocity=(0.0, 0.0), owner=None, seed=1, tick=0):
    return MatchState(
        players=list(players),
        ball=BallState(position=Vec(*ball), velocity=Vec(*velocity), owner=owner),
        seed=seed,
        tick=tick,
    )


def run(s: MatchState, ticks: int, actions: dict[PlayerKey, PlayerActions] | None = None):
    """Avanza `ticks` ticks repitiendo las mismas acciones. Devuelve el estado
    final y todos los eventos."""
    events = []
    for _ in range(ticks):
        result = step(s, actions)
        s = result.state
        events.extend(result.events)
    return s, events
