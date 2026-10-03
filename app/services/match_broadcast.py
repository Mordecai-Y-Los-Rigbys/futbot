"""Armado y envío del tick a los suscriptores de un partido."""

import asyncio
import json
from dataclasses import dataclass

from app.services.match_connection_manager import MatchConnectionManager
from app.simulation.match_rules import Event, TickResult
from app.simulation.state import Team

# Un tick dura 50 ms y el alcance pide tick + emisión < 100 ms: un suscriptor
# que no acepta el mensaje en ese tiempo se considera lento y se lo corta.
SEND_TIMEOUT = 0.1
SLOW_CLIENT_CODE = 1013
SLOW_CLIENT_REASON = "slowClient"


@dataclass(frozen=True)
class TickContext:
    """Datos fijos del partido que necesitan los eventos del tick."""

    club_1: str  # club1
    club_2: str  # club2
    countdown_seconds: int


def _r(value: float) -> float:
    return round(value, 2)


def _position(vector) -> dict:
    return {"x": _r(vector.x), "y": _r(vector.y)}


def _event(result: TickResult, ctx: TickContext) -> dict | None:
    if result.event is Event.PERIOD_START:
        return {
            "type": "periodStart",
            "periodNumber": result.period,
            "countdownSeconds": ctx.countdown_seconds,
        }
    if result.event is Event.GOAL:
        club = ctx.club_1 if result.scoring_team is Team.HOME else ctx.club_2
        return {"type": "goal", "scoringClub": club}
    if result.event is Event.MATCH_END:
        return {
            "type": "matchEnd",
            "result": {"score1": result.score_1, "score2": result.score_2},
        }
    return None


def build_tick_payload(result: TickResult, ctx: TickContext) -> dict:
    """TickPayload del AsyncAPI. Posiciones absolutas con 2 decimales.

    club1 = score1, club2 = score2. Nunca incluye
    comportamientos. Si más adelante se suma algo propio de cada usuario, hay
    que serializar adentro del loop de broadcast_tick con el user_id de cada
    suscriptor.
    """
    state = result.state
    return {
        "type": "tick",
        "players": [
            {"playerId": p.player_id, "position": _position(p.position)}
            for p in state.players
        ],
        "ballPosition": _position(state.ball.position),
        "score1": result.score_1,
        "score2": result.score_2,
        "elapsedTime": int(result.elapsed),
        "phase": result.phase.value,
        "event": _event(result, ctx),
    }


async def _send(websocket, text: str, timeout: float) -> None:
    """Nunca lanza: un suscriptor caído o lento no puede frenar a los demás."""
    try:
        await asyncio.wait_for(websocket.send_text(text), timeout)
        return
    except Exception:
        pass
    try:
        # El endpoint recibe el disconnect y hace release() del cupo.
        await asyncio.wait_for(
            websocket.close(code=SLOW_CLIENT_CODE, reason=SLOW_CLIENT_REASON), timeout
        )
    except Exception:
        pass


async def broadcast_tick(
    manager: MatchConnectionManager,
    match_id: int,
    payload: dict,
    timeout: float = SEND_TIMEOUT,
) -> None:
    subscribers = manager.subscribers(match_id)  # copia: puede cambiar mientras se envía
    if not subscribers:
        return
    text = json.dumps(payload, separators=(",", ":"))
    await asyncio.gather(*(_send(ws, text, timeout) for ws, _user_id in subscribers))