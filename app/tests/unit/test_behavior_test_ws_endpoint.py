"""WebSocket de la prueba de un comportamiento: /ws/behaviors/{id}/test."""

import asyncio
import time
from contextlib import contextmanager
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.ws_behavior_test_deps import (
    get_behavior_test_handshake_scope,
    get_behavior_test_runner,
    get_behavior_test_slots,
)
from app.main import app
from app.services import behavior_test_handshake
from app.services.behavior_test_handshake import BehaviorTestHandshakeService
from app.services.behavior_test_runner import BehaviorTestRunner
from app.services.behavior_test_slots import BehaviorTestSlots
from app.simulation import constants as C
from app.tests.unit import behavior_test_tick_schema as schema
from app.tests.unit.behavior_test_fakes import (
    LINEUP,
    NOW,
    OTHER_ID,
    TESTED_ID,
    USER_ID,
    FakeLineupRepo,
    FakeTestTokenRepo,
    lineup_members,
)

COUNTDOWN_TICKS = 3 * C.TICKS_PER_SECOND
TEST_TICKS = COUNTDOWN_TICKS + 3 * 60 * C.TICKS_PER_SECOND


async def no_wait(_seconds):
    await asyncio.sleep(0)  # deja correr al event loop, sin esperar los 50 ms


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(behavior_test_handshake, "_utcnow", lambda: NOW)


@pytest.fixture()
def tokens():
    repo = FakeTestTokenRepo()
    repo.add()
    return repo


@pytest.fixture()
def lineups():
    return FakeLineupRepo()


@pytest.fixture()
def slots():
    return BehaviorTestSlots()


@pytest.fixture()
def runner():
    """A tiempo real: los tests de handshake no necesitan la prueba entera."""
    return BehaviorTestRunner(seed_factory=lambda: 1)


@pytest.fixture()
def fast_runner(client):
    """Sin esperar entre ticks: para recorrer muchos ticks rápido."""
    app.dependency_overrides[get_behavior_test_runner] = lambda: BehaviorTestRunner(
        sleep=no_wait, seed_factory=lambda: 1
    )


@pytest.fixture()
def client(tokens, lineups, slots, runner):
    service = BehaviorTestHandshakeService(tokens, lineups)

    @contextmanager
    def scope():
        yield service

    app.dependency_overrides[get_behavior_test_handshake_scope] = lambda: scope
    app.dependency_overrides[get_behavior_test_slots] = lambda: slots
    app.dependency_overrides[get_behavior_test_runner] = lambda: runner
    yield TestClient(app)
    app.dependency_overrides.clear()


def url(behavior_id=TESTED_ID, token="tok"):
    path = f"/ws/behaviors/{behavior_id}/test"
    return path + ("" if token is None else f"?token={token}")


def rejection(client, path) -> tuple[int, str]:
    """(close code, reason) con el que el server cierra el handshake."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path) as ws:
            ws.receive_text()
    return exc.value.code, exc.value.reason


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def play_whole_test(client):
    """Todos los testTick de una prueba completa y el cierre del servidor."""
    ticks = []
    with client.websocket_connect(url()) as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            while True:
                ticks.append(ws.receive_json())
    return ticks, (exc.value.code, exc.value.reason)


# --- handshake aceptado -------------------------------------------------------


def test_the_test_starts_right_away_with_a_3_second_countdown(client, slots):
    with client.websocket_connect(url()) as ws:
        first = ws.receive_json()
        assert slots.is_open(USER_ID)

    schema.TestTickPayload.model_validate(first)
    assert first["phase"] == "countdown"
    assert first["event"] == {"type": "testStart", "countdownSeconds": 3}


# --- handshake rechazado: un test por cierre ----------------------------------


@pytest.mark.parametrize("token", [None, "", "no-existe", "x" * 100])
def test_missing_or_unknown_token_is_4401_token_invalid(client, slots, token):
    assert rejection(client, url(token=token)) == (4401, "tokenInvalid")
    assert not slots.is_open(USER_ID)


def test_expired_token_is_4401_token_expired(client, tokens):
    tokens.add("viejo", expires_at=NOW - timedelta(seconds=1))
    assert rejection(client, url(token="viejo")) == (4401, "tokenExpired")


@pytest.mark.parametrize("behavior_id", [OTHER_ID, "abc", "05"])
def test_token_of_another_behavior_is_4403(client, behavior_id):
    assert rejection(client, url(behavior_id=behavior_id)) == (4403, "tokenBehaviorMismatch")


def test_deleted_tested_behavior_is_4404(client, tokens, lineups):
    # Nadie de la alineación juega con el behavior probado: solo lo pide la URL.
    lineup = [(player_id, club, role, OTHER_ID) for player_id, club, role, _ in LINEUP]
    tokens.add(members=lineup_members(lineup))
    del lineups.codes[TESTED_ID]
    assert rejection(client, url()) == (4404, "behaviorNotFound")


def test_deleted_behavior_of_the_lineup_is_4404(client, lineups):
    del lineups.codes[OTHER_ID]
    assert rejection(client, url()) == (4404, "behaviorNotFound")


def test_only_the_first_failure_is_reported(client, tokens, lineups):
    tokens.add("viejo", behavior_id=OTHER_ID, expires_at=NOW - timedelta(seconds=1))
    del lineups.codes[OTHER_ID]
    assert rejection(client, url(token="viejo")) == (4401, "tokenExpired")
    assert rejection(client, url(behavior_id=OTHER_ID)) == (4403, "tokenBehaviorMismatch")


# --- una prueba a la vez ------------------------------------------------------


def test_a_second_simultaneous_test_of_the_same_user_is_4429(client, slots):
    with client.websocket_connect(url()) as ws:
        ws.receive_json()
        assert rejection(client, url()) == (4429, "tooManyConnections")
        assert slots.is_open(USER_ID)  # la primera sigue


def test_closing_the_connection_releases_the_slot(client, slots):
    with client.websocket_connect(url()) as ws:
        ws.receive_json()
    assert wait_until(lambda: not slots.is_open(USER_ID))

    with client.websocket_connect(url()) as ws:  # con el mismo token arranca otra
        assert ws.receive_json()["event"]["type"] == "testStart"


# --- la prueba ----------------------------------------------------------------


def test_incoming_messages_are_ignored(client, slots):
    with client.websocket_connect(url()) as ws:
        ws.receive_json()
        ws.send_text("hola")
        ws.send_json({"type": "pause"})
        # Se mira el cupo antes de leer: si la prueba se cortó, leer se quedaría esperando.
        assert not wait_until(lambda: not slots.is_open(USER_ID), timeout=0.5)
        assert ws.receive_json()["type"] == "testTick"  # sigue, sin respuesta ni cierre


def test_the_whole_test_respects_the_contract_and_ends_with_1000_test_end(
    client, fast_runner, slots
):
    ticks, closing = play_whole_test(client)

    for tick in ticks:
        schema.TestTickPayload.model_validate(tick)
    assert len(ticks) == TEST_TICKS
    assert (ticks[-1]["phase"], ticks[-1]["event"]) == (
        "finished",
        {"type": "testEnd", "reason": "timeLimit"},
    )
    assert closing == (1000, "testEnd")
    assert wait_until(lambda: not slots.is_open(USER_ID))


def test_each_player_plays_in_its_club_and_role_with_its_behavior(client, fast_runner, lineups):
    lineups.codes[OTHER_ID] = "go_to(0, 0)"  # solo el jugador 4 (club2) se mueve
    with client.websocket_connect(url()) as ws:
        ticks = [ws.receive_json() for _ in range(COUNTDOWN_TICKS + C.TICKS_PER_SECOND)]

    def positions(tick):
        return {player["playerId"]: player["position"] for player in tick["players"]}

    before, after = positions(ticks[0]), positions(ticks[-1])
    assert all(before[player_id]["x"] < 50 for player_id in (1, 2, 3))  # club1, a la izquierda
    assert all(before[player_id]["x"] > 50 for player_id in (4, 5, 6))  # club2, a la derecha
    # Cada rol tiene su lugar: el delantero adelante y el defensor atrás.
    assert before[3]["x"] < before[2]["x"] < before[1]["x"]
    assert before[4]["x"] < before[5]["x"] < before[6]["x"]
    assert [player_id for player_id in before if after[player_id] != before[player_id]] == [4]


def test_a_behavior_that_fails_to_compile_closes_with_1011(client, lineups, slots):
    lineups.codes[OTHER_ID] = "def ("
    with client.websocket_connect(url()) as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert (exc.value.code, exc.value.reason) == (1011, "testError")
    assert wait_until(lambda: not slots.is_open(USER_ID))
