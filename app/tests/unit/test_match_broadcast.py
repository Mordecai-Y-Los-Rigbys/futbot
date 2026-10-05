import asyncio
import time

import pytest

from app.services import match_broadcast
from app.services.match_broadcast import broadcast_tick
from app.services.match_connection_manager import MatchConnectionManager

TIMEOUT = 0.2
PAYLOAD = {"type": "tick"}


class HealthyWs:
    def __init__(self):
        self.received, self.closed = [], None

    async def send_text(self, text):
        self.received.append(text)

    async def close(self, code=1000, reason=None):
        self.closed = (code, reason)


class HangingWs:
    """Cliente colgado: ni acepta mensajes ni termina de cerrar."""

    def __init__(self):
        self.close_called = None

    async def send_text(self, text):
        await asyncio.sleep(10)

    async def close(self, code=1000, reason=None):
        self.close_called = (code, reason)
        await asyncio.sleep(10)


@pytest.fixture()
def manager():
    return MatchConnectionManager()


def connect(manager, ws, match_id=1, user_id=7):
    manager.reserve(match_id, user_id)
    manager.subscribe(match_id, user_id, ws)


def broadcast(manager, timeout=TIMEOUT):
    async def main():
        began = time.perf_counter()
        await broadcast_tick(manager, 1, PAYLOAD, timeout)
        elapsed = time.perf_counter() - began
        await asyncio.gather(*list(match_broadcast._closing))
        return elapsed

    return asyncio.run(main())


def test_slow_client_frees_its_slot_and_subscription_right_away(manager):
    hung = HangingWs()
    connect(manager, hung)

    broadcast(manager)

    assert manager.count(1, 7) == 0
    assert manager.subscribers(1) == []


def test_slow_client_is_closed_with_1013_slow_client(manager):
    hung = HangingWs()
    connect(manager, hung)

    broadcast(manager)

    assert hung.close_called == (1013, "slowClient")


def test_tick_does_not_wait_for_the_close(manager):
    connect(manager, HangingWs())

    elapsed = broadcast(manager)

    # Un solo timeout (el del send). Si esperara también el close serían 2 x TIMEOUT.
    assert elapsed < 1.5 * TIMEOUT


def test_healthy_clients_are_not_affected(manager):
    healthy, hung = HealthyWs(), HangingWs()
    connect(manager, healthy)
    connect(manager, hung, user_id=8)

    broadcast(manager)

    assert len(healthy.received) == 1 and healthy.closed is None
    assert [ws for ws, _ in manager.subscribers(1)] == [healthy]
    assert manager.count(1, 7) == 1 and manager.count(1, 8) == 0


def test_evicting_one_connection_keeps_the_users_other_connections(manager):
    healthy, hung = HealthyWs(), HangingWs()
    connect(manager, healthy)
    connect(manager, hung)  # mismo usuario

    broadcast(manager)
    manager.release(1, 7, hung)  # el finally del endpoint, más tarde

    assert manager.count(1, 7) == 1
    assert manager.subscribers(1) == [(healthy, 7)]


def test_user_with_five_dead_connections_can_reconnect(manager):
    # El caso del review: wifi cortado varias veces, no debe quedar un 429.
    for _ in range(5):
        connect(manager, HangingWs())

    broadcast(manager)

    manager.reserve(1, 7)  # no debe lanzar tooManyConnections
    assert manager.count(1, 7) == 1


def test_close_task_is_released_after_it_finishes(manager):
    connect(manager, HangingWs())

    broadcast(manager)

    assert match_broadcast._closing == set()


def test_no_subscribers_is_a_noop(manager):
    assert broadcast(manager) < TIMEOUT