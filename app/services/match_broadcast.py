"""Armado y envío del tick a los suscriptores de un partido."""

import asyncio
import json
from dataclasses import dataclass
from fastapi import WebSocket

from app.services.match_connection_manager import MatchConnectionManager
from app.simulation.geometry import Vec
from app.simulation.match_rules import Event, Phase, TickResult
from app.simulation.penalties import PenaltyKick, ShootoutStatus
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


def _position(vector: Vec) -> dict:
    return {"x": _r(vector.x), "y": _r(vector.y)}


def _club(team: Team) -> str:
    return "club1" if team is Team.HOME else "club2"


def penalty_kick_record(kick: PenaltyKick) -> dict:
    return {
        "club": _club(kick.team),
        "kickerId": kick.kicker_id,
        "kickerName": kick.kicker_name,
        "round": kick.round,
        "scored": kick.scored,
    }


def penalty_shootout(status: ShootoutStatus) -> dict:
    return {
        "score1": status.score_1,
        "score2": status.score_2,
        "winner": _club(status.winner),
        "kicks": [penalty_kick_record(k) for k in status.kicks],
    }


def _penalty_current(result: TickResult) -> dict | None:
    if result.phase is not Phase.PENALTIES:
        return None
    current = result.shootout.current
    return {
        "club": _club(current.team),
        "kickerId": current.kicker_id,
        "kickerName": current.kicker_name,
        "defenderId": current.defender_id,
        "defenderName": current.defender_name,
    }


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
    if result.event is Event.PAUSE:
        return {
            "type": "pause",
            "reason": result.pause_reason.value,
            "durationSeconds": result.pause_duration_seconds,
        }
    if result.event is Event.PENALTIES_START:
        return {"type": "penaltiesStart"}
    if result.event is Event.PENALTY_KICK:
        return {"type": "penaltyKick", **penalty_kick_record(result.penalty_kick)}
    if result.event is Event.MATCH_END:
        shootout = result.shootout
        return {
            "type": "matchEnd",
            "result": {
                "score1": result.score_1,
                "score2": result.score_2,
                "penalties": penalty_shootout(shootout) if shootout is not None else None,
            },
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
    shootout = result.shootout
    in_penalties = result.phase is Phase.PENALTIES
    return {
        "type": "tick",
        "players": [
            {"playerId": p.player_id, "position": _position(p.position)} for p in state.players
        ],
        "ballPosition": _position(state.ball.position),
        "score1": result.score_1,
        "score2": result.score_2,
        "penaltyScore1": shootout.score_1 if shootout else 0,
        "penaltyScore2": shootout.score_2 if shootout else 0,
        "penaltyKicks": [penalty_kick_record(k) for k in shootout.kicks] if shootout else [],
        "penaltyCurrent": _penalty_current(result),
        "penaltyCountdownSeconds": shootout.countdown_seconds if in_penalties else None,
        "penaltyRemainingSeconds": shootout.remaining_seconds if in_penalties else None,
        "elapsedTime": int(result.elapsed),
        "pauseRemainingSeconds": result.pause_remaining_seconds,  # None fuera de la pausa
        # Pausas que no empezaron (3 a 0), sin la en curso. Estado completo en cada
        # tick: igual para jugadores y espectadores, y correcto en el primer tick de
        # quien se conecta tarde o se reconecta.
        "pausesLeft": result.pauses_left,
        "phase": result.phase.value,
        "event": _event(result, ctx),
    }


_closing: set[asyncio.Task] = set()  # referencia fuerte: si no, el GC puede matar la tarea


async def _close(websocket: WebSocket, timeout: float) -> None:
    try:
        await asyncio.wait_for(
            websocket.close(code=SLOW_CLIENT_CODE, reason=SLOW_CLIENT_REASON), timeout
        )
    except Exception:
        pass


async def _send(
    manager: MatchConnectionManager,
    match_id: int,
    user_id: int,
    websocket: WebSocket,
    text: str,
    timeout: float,
) -> None:
    """Nunca lanza: un suscriptor caído o lento no puede frenar a los demás."""
    try:
        await asyncio.wait_for(websocket.send_text(text), timeout)
        return
    except Exception:
        pass
    manager.evict(match_id, user_id, websocket)  # cupo libre al toque
    task = asyncio.create_task(_close(websocket, timeout))  # sin esperar dentro del gather
    _closing.add(task)
    task.add_done_callback(_closing.discard)


async def broadcast_tick(
    manager: MatchConnectionManager, match_id: int, payload: dict, timeout: float = SEND_TIMEOUT
) -> None:
    """Envía el tick a todos los suscriptores del partido, en paralelo.

    Un suscriptor que no recibe el mensaje en `timeout` segundos se libera del
    manager en el momento y se cierra con 1013 / slowClient, sin frenar al resto.
    """

    subscribers = manager.subscribers(match_id)
    if not subscribers:
        return
    text = json.dumps(payload, separators=(",", ":"))
    await asyncio.gather(
        *(_send(manager, match_id, uid, ws, text, timeout) for ws, uid in subscribers)
    )
