"""Armado del `testTick` (TestTickPayload del AsyncAPI)."""

from app.services.match_broadcast import club, position
from app.simulation.constants import BEHAVIOR_TEST_COUNTDOWN_SECONDS
from app.simulation.match_rules import Event, TickResult


def _event(result: TickResult) -> dict | None:
    if result.event is Event.PERIOD_START:
        return {"type": "testStart", "countdownSeconds": BEHAVIOR_TEST_COUNTDOWN_SECONDS}
    if result.event is Event.GOAL:
        return {"type": "goal", "club": club(result.scoring_team)}
    if result.event is Event.MATCH_END:
        return {"type": "testEnd", "reason": "timeLimit"}
    return None


def build_test_tick_payload(result: TickResult) -> dict:
    """Como el `tick` del partido, sin nombres de club, pausas ni penales."""
    state = result.state
    return {
        "type": "testTick",
        "players": [
            {"playerId": player.player_id, "position": position(player.position)}
            for player in state.players
        ],
        "ballPosition": position(state.ball.position),
        "score1": result.score_1,
        "score2": result.score_2,
        "elapsedTime": int(result.elapsed),
        "phase": result.phase.value,
        "event": _event(result),
    }
