import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.match_expiry_abstract import (
    AbstractMatchExpiryRepository,
    WaitingFriendlyData,
)
from app.services import friendly_expiry
from app.services.friendly_expiry import FriendlyExpiryService
from app.services.match_timing import MAX_FRIENDLY_WAIT

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
SHORT = timedelta(milliseconds=30)


class FakeExpiryRepo(AbstractMatchExpiryRepository):
    def __init__(self):
        self.cancellable: set[int] = set()  # amistosos que siguen en espera
        self.cancel_calls: list[int] = []
        self.waiting: list[WaitingFriendlyData] = []

    def cancel_if_waiting_friendly(self, match_id):
        self.cancel_calls.append(match_id)
        return match_id in self.cancellable

    def list_waiting_friendlies(self):
        return self.waiting


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(friendly_expiry, "_utcnow", lambda: NOW)


@pytest.fixture()
def repo():
    return FakeExpiryRepo()


def build(repo, wait=SHORT):
    closed: list[int] = []

    async def close_match(match_id):
        closed.append(match_id)

    @contextmanager
    def scope():
        yield repo

    return FriendlyExpiryService(scope, close_match, wait=wait), closed


def run(coro_fn):
    asyncio.run(coro_fn())


# --- el plazo ---------------------------------------------------------------


def test_default_wait_is_max_friendly_wait(repo):
    @contextmanager
    def scope():
        yield repo

    async def close(_):
        pass

    assert FriendlyExpiryService(scope, close).wait == MAX_FRIENDLY_WAIT


# --- vencimiento -------------------------------------------------------------


def test_waiting_friendly_is_cancelled_and_its_connections_closed(repo):
    repo.cancellable = {1}
    service, closed = build(repo)

    async def body():
        service.schedule(1)
        await asyncio.sleep(0.3)

    run(body)

    assert repo.cancel_calls == [1]
    assert closed == [1]


def test_friendly_that_got_a_rival_is_not_closed(repo):
    # cancel_if_waiting_friendly devuelve False: el rival ganó la carrera
    service, closed = build(repo)

    async def body():
        service.schedule(1)
        await asyncio.sleep(0.3)

    run(body)

    assert repo.cancel_calls == [1]
    assert closed == []


def test_nothing_happens_before_the_deadline(repo):
    repo.cancellable = {1}
    service, closed = build(repo, wait=timedelta(hours=1))

    async def body():
        service.schedule(1)
        await asyncio.sleep(0.1)
        service.shutdown()

    run(body)

    assert repo.cancel_calls == []
    assert closed == []


def test_unschedule_prevents_the_cancellation(repo):
    repo.cancellable = {1}
    service, closed = build(repo)

    async def body():
        service.schedule(1)
        service.unschedule(1)
        await asyncio.sleep(0.3)

    run(body)

    assert repo.cancel_calls == []
    assert closed == []


def test_scheduling_again_replaces_the_previous_timer(repo):
    repo.cancellable = {1}
    service, closed = build(repo)

    async def body():
        service.schedule(1)
        service.schedule(1)
        await asyncio.sleep(0.3)

    run(body)

    assert repo.cancel_calls == [1]  # un solo vencimiento
    assert closed == [1]


def test_a_failure_does_not_kill_the_service(repo, caplog):
    def boom(match_id):
        raise RuntimeError("base caída")

    repo.cancel_if_waiting_friendly = boom
    service, closed = build(repo)

    async def body():
        service.schedule(1)
        await asyncio.sleep(0.3)

    run(body)  # no propaga la excepción

    assert closed == []
    assert "No se pudo caducar" in caplog.text


# --- recuperación al arrancar -----------------------------------------------------


def test_recover_cancels_overdue_now_and_reschedules_the_rest(repo):
    repo.cancellable = {1, 2}
    repo.waiting = [
        WaitingFriendlyData(match_id=1, created_at=NOW - timedelta(hours=2)),  # vencido
        WaitingFriendlyData(match_id=2, created_at=NOW - timedelta(minutes=30)),
    ]
    service, closed = build(repo, wait=timedelta(hours=1))

    async def body():
        await service.recover()
        await asyncio.sleep(0.3)
        assert 1 not in service._tasks  # ya se ejecutó
        assert 2 in service._tasks  # queda media hora
        service.shutdown()

    run(body)

    assert repo.cancel_calls == [1]
    assert closed == [1]


def test_recover_with_nothing_waiting_is_a_noop(repo):
    service, closed = build(repo)

    async def body():
        await service.recover()

    run(body)

    assert repo.cancel_calls == [] and closed == []


def test_shutdown_cancels_pending_timers(repo):
    repo.cancellable = {1}
    service, closed = build(repo, wait=timedelta(hours=1))

    async def body():
        service.schedule(1)
        service.shutdown()
        await asyncio.sleep(0.1)

    run(body)

    assert service._tasks == {}
    assert repo.cancel_calls == []