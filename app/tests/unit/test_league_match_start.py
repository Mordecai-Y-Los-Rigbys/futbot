import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.league_match_start_abstract import (
    AbstractLeagueMatchStartRepository,
    PendingLeagueMatch,
)
from app.services import league_match_start
from app.services.league_match_start import LeagueMatchStartService

NOW = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)
SOON = NOW + timedelta(milliseconds=100)
WAIT = 0.3


class FakeRepo(AbstractLeagueMatchStartRepository):
    def __init__(self, ready=True, pending=(), failures=0):
        self.ready = ready
        self.pending = list(pending)
        self.failures = failures
        self.attempts = 0
        self.listed = []

    def is_ready_to_start(self, match_id):
        self.attempts += 1
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("boom")
        return self.ready

    def list_pending_start(self, league_id=None):
        self.listed.append(league_id)
        return list(self.pending)


def make_service(repo):
    @contextmanager
    def scope():
        yield repo

    started = []

    async def on_start(match_id):
        started.append(match_id)

    return LeagueMatchStartService(scope, on_start), started


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(league_match_start, "_utcnow", lambda: NOW)


@pytest.fixture()
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(league_match_start, "START_RETRY_DELAY", 0)


def run(scenario):
    return asyncio.run(scenario())


def test_a_match_whose_time_already_passed_starts_right_away():
    service, started = make_service(FakeRepo())

    async def scenario():
        service.schedule(10, NOW - timedelta(hours=1))
        await asyncio.sleep(0.05)

    run(scenario)
    assert started == [10]


def test_a_match_that_is_no_longer_scheduled_does_not_start():
    service, started = make_service(FakeRepo(ready=False))
    assert run(lambda: service.start(10)) is False
    assert started == []


def test_a_failure_of_the_simulation_does_not_propagate():
    @contextmanager
    def scope():
        yield FakeRepo()

    async def on_start(match_id):
        raise RuntimeError("boom")

    service = LeagueMatchStartService(scope, on_start)
    assert run(lambda: service.start(10)) is True


def test_retries_are_bounded(no_retry_delay):
    repo = FakeRepo(failures=10)
    service, started = make_service(repo)

    async def scenario():
        service.schedule(10, NOW)
        await asyncio.sleep(0.1)

    run(scenario)
    assert repo.attempts == league_match_start.START_RETRIES and started == []


def test_starting_a_league_schedules_its_pending_matches():
    repo = FakeRepo(pending=[PendingLeagueMatch(match_id=m, scheduled_at=NOW) for m in (10, 11)])
    service, started = make_service(repo)

    async def scenario():
        await service.schedule_league(5)
        await asyncio.sleep(0.05)

    run(scenario)
    assert repo.listed == [5]
    assert started == [10, 11]


def test_recover_schedules_the_pending_matches_of_every_league():
    repo = FakeRepo(pending=[PendingLeagueMatch(match_id=10, scheduled_at=NOW)])
    service, started = make_service(repo)

    async def scenario():
        await service.recover()
        await asyncio.sleep(0.05)

    run(scenario)
    assert repo.listed == [None]
    assert started == [10]


def test_scheduling_again_replaces_the_previous_timer():
    service, started = make_service(FakeRepo())

    async def scenario():
        service.schedule(10, SOON)
        service.schedule(10, SOON)
        await asyncio.sleep(WAIT)

    run(scenario)
    assert started == [10]


def test_shutdown_cancels_every_pending_start():
    service, started = make_service(FakeRepo())

    async def scenario():
        service.schedule(10, SOON)
        service.schedule(11, SOON)
        service.shutdown()
        await asyncio.sleep(WAIT)

    run(scenario)
    assert started == []
