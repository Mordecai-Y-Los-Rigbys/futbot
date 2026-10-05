import asyncio
from contextlib import contextmanager
from datetime import timedelta

import pytest

from app.repositories.match_start_abstract import AbstractMatchStartRepository
from app.services import friendly_start
from app.services.friendly_start import FriendlyStartService
from app.services.match_timing import FRIENDLY_COUNTDOWN

FAST = timedelta(milliseconds=20)
WAIT = 0.4  # segundos de espera real: muy por encima de FAST


class FakeStartRepo(AbstractMatchStartRepository):
    def __init__(self, ready=True, pending=(), failures=0):
        self.ready = ready
        self.pending = list(pending)
        self.failures = failures
        self.attempts = 0
        self.triggered = []

    def is_ready_to_start(self, match_id):
        self.attempts += 1
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("boom")
        if self.ready:
            self.triggered.append(match_id)
        return self.ready

    def list_pending_start(self):
        return list(self.pending)


def make_service(repo, on_start=None, countdown=FAST):
    @contextmanager
    def scope():
        yield repo

    return FriendlyStartService(scope, on_start, countdown)


@pytest.fixture()
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(friendly_start, "START_RETRY_DELAY", 0)


def test_default_countdown_is_three_seconds():
    assert FRIENDLY_COUNTDOWN == timedelta(seconds=3)
    assert make_service(FakeStartRepo(), countdown=FRIENDLY_COUNTDOWN).countdown == timedelta(seconds=3)


def test_start_returns_false_and_skips_on_start_when_not_ready():
    repo = FakeStartRepo(ready=False)
    calls = []

    async def on_start(match_id):
        calls.append(match_id)

    service = make_service(repo, on_start)
    assert asyncio.run(service.start(100)) is False
    assert calls == []


def test_on_start_failure_does_not_propagate():
    repo = FakeStartRepo()

    async def on_start(match_id):
        raise RuntimeError("simulación caída")

    service = make_service(repo, on_start)
    assert asyncio.run(service.start(100)) is True
    assert repo.triggered == [100]


def test_unschedule_prevents_the_start():
    repo = FakeStartRepo()
    service = make_service(repo)

    async def scenario():
        service.schedule(100)
        service.unschedule(100)
        await asyncio.sleep(WAIT)

    asyncio.run(scenario())
    assert repo.triggered == []


def test_scheduling_again_replaces_the_previous_timer():
    repo = FakeStartRepo()
    service = make_service(repo)

    async def scenario():
        service.schedule(100)
        service.schedule(100)
        await asyncio.sleep(WAIT)

    asyncio.run(scenario())
    assert repo.triggered == [100]  # una sola vez


def test_a_failure_is_retried(no_retry_delay):
    repo = FakeStartRepo(failures=1)
    service = make_service(repo)

    async def scenario():
        service.schedule(100)
        await asyncio.sleep(WAIT)

    asyncio.run(scenario())
    assert repo.attempts == 2
    assert repo.triggered == [100]


def test_retries_are_bounded(no_retry_delay):
    repo = FakeStartRepo(failures=99)
    service = make_service(repo)

    async def scenario():
        service.schedule(100)
        await asyncio.sleep(WAIT)

    asyncio.run(scenario())
    assert repo.attempts == friendly_start.START_RETRIES
    assert repo.triggered == []


def test_recover_reschedules_the_pending_matches():
    repo = FakeStartRepo(pending=[1, 2])
    service = make_service(repo)

    async def scenario():
        await service.recover()
        await asyncio.sleep(WAIT)

    asyncio.run(scenario())
    assert sorted(repo.triggered) == [1, 2]


def test_recover_with_nothing_pending_is_a_noop():
    service = make_service(FakeStartRepo())
    asyncio.run(service.recover())
    assert service._tasks == {}


def test_shutdown_cancels_pending_timers():
    repo = FakeStartRepo()
    service = make_service(repo, countdown=timedelta(milliseconds=100))

    async def scenario():
        service.schedule(100)
        service.shutdown()
        await asyncio.sleep(WAIT)

    asyncio.run(scenario())
    assert repo.triggered == []
    

def test_countdown_waits_three_seconds_before_starting(monkeypatch):
    from types import SimpleNamespace

    async def scenario():
        waiting = asyncio.Event()
        release = asyncio.Event()
        requested_delays = []
        callbacks = []

        async def controlled_sleep(seconds):
            requested_delays.append(seconds)
            waiting.set()
            await release.wait()

        # Reemplazar la referencia del módulo, sin modificar
        # asyncio.sleep globalmente para el resto de la aplicación.
        controlled_asyncio = SimpleNamespace(
            sleep=controlled_sleep,
            get_running_loop=asyncio.get_running_loop,
            CancelledError=asyncio.CancelledError,
        )
        monkeypatch.setattr(
            friendly_start, "asyncio", controlled_asyncio
        )

        repo = FakeStartRepo()

        async def on_start(match_id):
            callbacks.append(match_id)

        service = make_service(
            repo,
            on_start=on_start,
            countdown=FRIENDLY_COUNTDOWN,
        )

        service.schedule(100)
        task = service._tasks[100]

        try:
            # El timeout solo detecta un bloqueo; no simula el tiempo.
            await asyncio.wait_for(waiting.wait(), timeout=5)

            assert requested_delays == [3.0]
            assert repo.attempts == 0
            assert repo.triggered == []
            assert callbacks == []

            release.set()
            await asyncio.wait_for(task, timeout=5)

            assert repo.attempts == 1
            assert repo.triggered == [100]
            assert callbacks == [100]
        finally:
            service.shutdown()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())