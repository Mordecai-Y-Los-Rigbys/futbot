"""El schema del tick (contrato AsyncAPI) y los ticks que realmente emite el servidor."""

import json

import pytest
from pydantic import ValidationError

from app.services.match_broadcast import TickContext, build_tick_payload
from app.simulation.match_rules import Event, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.simulate import simulate_match
from app.simulation.state import Team
from app.simulation.run import default_team as make_team
from app.tests.unit.tick_schema import TickPayload

CTX = TickContext(club_1="Club Uno", club_2="Club Dos", countdown_seconds=1)


def payload(**over) -> dict:
    base = {
        "type": "tick",
        "players": [{"playerId": i, "position": {"x": 10.0 + i, "y": 30.0}} for i in range(1, 7)],
        "ballPosition": {"x": 50.0, "y": 30.0},
        "score1": 0,
        "score2": 0,
        "elapsedTime": 5,
        "phase": "playing",
        "event": None,
    }
    base.update(over)
    return base


# --- el schema acepta lo que define el contrato -------------------------------


@pytest.mark.parametrize(
    "over",
    [
        {},
        {
            "phase": "countdown",
            "elapsedTime": 0,
            "event": {"type": "periodStart", "periodNumber": 1, "countdownSeconds": 10},
        },
        {"score1": 1, "event": {"type": "goal", "scoringClub": "Club Uno"}},
        {
            "score1": 1,
            "ballPosition": {"x": 100.4, "y": 30.0},  # pelota dentro del arco
            "event": {"type": "goal", "scoringClub": "Club Uno"},
        },
        {"phase": "paused", "event": {"type": "pause", "reason": "halftime"}},
        {
            "score1": 2,
            "score2": 1,
            "phase": "finished",
            "event": {"type": "matchEnd", "result": {"score1": 2, "score2": 1}},
        },
        # gol en el último tick: llega matchEnd, no goal, con la pelota en el arco
        {
            "score1": 1,
            "phase": "finished",
            "ballPosition": {"x": 100.4, "y": 30.0},
            "event": {"type": "matchEnd", "result": {"score1": 1, "score2": 0}},
        },
    ],
)
def test_valid_payloads(over):
    TickPayload.model_validate(payload(**over))


# --- ...y rechaza lo que no ---------------------------------------------------


def without(key):
    p = payload()
    del p[key]
    return p


@pytest.mark.parametrize(
    "key", ["type", "players", "ballPosition", "score1", "score2", "elapsedTime", "phase", "event"]
)
def test_every_key_is_required_including_a_null_event(key):
    with pytest.raises(ValidationError):
        TickPayload.model_validate(without(key))


@pytest.mark.parametrize(
    "over",
    [
        {"extra": 1},  # clave de más
        {"type": "marcador"},
        {"score1": "1"},  # sin conversión de tipos
        {"score1": True},
        {"score1": -1},
        {"elapsedTime": 1.5},
        {"elapsedTime": "5"},
        {"phase": "waiting"},
        {"ballPosition": {"x": 50.0}},
        {"ballPosition": {"x": 50.0, "y": 30.0, "z": 0}},
        {"ballPosition": {"x": 50.0, "y": 61.0}},  # fuera de la cancha
        {"ballPosition": {"x": 101.0, "y": 30.0}},  # fuera de la cancha sin gol
        {"players": [{"playerId": "1", "position": {"x": 10.0, "y": 30.0}}]},
        {"players": [{"playerId": 1, "position": {"x": 101.0, "y": 30.0}}]},
        {"event": {"type": "tiro"}},  # evento desconocido
        {"event": {"type": "goal"}},  # falta scoringClub
        {
            "event": {"type": "periodStart", "periodNumber": 5, "countdownSeconds": 10},
            "phase": "countdown",
        },
        {"event": {"type": "pause", "reason": "lluvia"}, "phase": "paused"},
    ],
)
def test_invalid_payloads(over):
    with pytest.raises(ValidationError):
        TickPayload.model_validate(payload(**over))


@pytest.mark.parametrize(
    "over",
    [
        # matchEnd sin phase finished, y al revés
        {"event": {"type": "matchEnd", "result": {"score1": 0, "score2": 0}}},
        {"phase": "finished"},
        # el resultado no coincide con el marcador
        {
            "score1": 1,
            "phase": "finished",
            "event": {"type": "matchEnd", "result": {"score1": 0, "score2": 0}},
        },
        # evento en una fase que no le corresponde
        {"event": {"type": "periodStart", "periodNumber": 1, "countdownSeconds": 10}},
        {"phase": "countdown", "event": {"type": "goal", "scoringClub": "Club Uno"}},
        {"event": {"type": "pause", "reason": "hydration"}},
    ],
)
def test_phase_and_event_must_agree(over):
    with pytest.raises(ValidationError):
        TickPayload.model_validate(payload(**over))


# --- lo que realmente emite el servidor ---------------------------------------


def on_the_wire(result: TickResult) -> dict:
    # Pasa por JSON, como llega al cliente.
    return json.loads(json.dumps(build_tick_payload(result, CTX)))


def test_every_tick_of_a_simulated_match_follows_the_contract():
    ticks = simulate_match(
        make_team(), make_team(first_id=10), 10, seed=1, countdown_seconds=1
    ).ticks
    assert ticks
    for tick in ticks:
        TickPayload.model_validate(on_the_wire(tick))


def test_goal_tick_follows_the_contract():
    team_1, team_2 = make_team(), make_team(first_id=10)
    state = create_initial_state(team_1.players, team_2.players, 1)
    result = TickResult(5, Phase.PLAYING, Event.GOAL, state, 0, 1, 0.25, 0.75, 1, Team.AWAY)

    parsed = TickPayload.model_validate(on_the_wire(result))

    assert parsed.event.scoringClub == "Club Dos"
    assert (parsed.score1, parsed.score2) == (0, 1)


def test_goal_in_the_last_tick_arrives_as_match_end_with_the_score_updated():
    team_1, team_2 = make_team(), make_team(first_id=10)
    state = create_initial_state(team_1.players, team_2.players, 1)
    # Lo que arma MatchSession.advance() cuando el gol cae en el último tick.
    result = TickResult(99, Phase.FINISHED, Event.MATCH_END, state, 1, 0, 1.0, 0.0, 1, Team.HOME)

    parsed = TickPayload.model_validate(on_the_wire(result))

    assert parsed.event.type == "matchEnd"
    assert (parsed.event.result.score1, parsed.score1) == (1, 1)
