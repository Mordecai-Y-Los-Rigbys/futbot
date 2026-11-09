import asyncio
import json
import time

import pytest

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.services.league_fixture_channel import LeagueFixtureState
from app.services.league_next_match_channel import (
    NEXT_MATCH_CHANNEL,
    LeagueNextMatchManager,
    build_next_match_payload,
    pick_next_match,
)
from app.tests.unit.league_fixture_fakes import FakeFixtures, match
from app.tests.unit.league_participants_fakes import CREATOR_ID, FakeLeagues


def state(status=LeagueStatus.started, matches=None):
    return LeagueFixtureState(
        league_id=5,
        status=status,
        matches=[match(1, 7, 8)] if matches is None else matches,
    )


# --- partido siguiente --------------------------------------------------------


def test_the_started_match_comes_before_any_scheduled():
    matches = [match(1, 7, 8, hours=0), match(2, 7, 9, hours=1, status=MatchStatus.started)]
    assert pick_next_match(matches).id == 2


def test_without_a_started_match_it_is_the_first_scheduled_by_date():
    matches = [match(1, 7, 8, hours=2), match(2, 7, 9, hours=1), match(3, 8, 9, hours=3)]
    assert pick_next_match(matches).id == 2


def test_same_date_is_broken_by_id():
    matches = [match(4, 7, 8, hours=1), match(3, 7, 9, hours=1)]
    assert pick_next_match(matches).id == 3


def test_finished_matches_are_skipped():
    matches = [
        match(1, 7, 8, hours=0, status=MatchStatus.finished, score=(1, 0)),
        match(2, 7, 9, hours=1),
    ]
    assert pick_next_match(matches).id == 2


def test_without_pending_matches_there_is_none():
    assert pick_next_match([match(1, 7, 8, status=MatchStatus.finished, score=(1, 0))]) is None


# --- payload ------------------------------------------------------------------


def test_payload_matches_the_contract():
    assert build_next_match_payload(state(), user_id=7) == {
        "type": "leagueNextMatch",
        "leagueStatus": "started",
        "match": {
            "id": 1,
            "leagueId": 5,
            "name": None,
            "status": "scheduled",
            "club1": {"id": 7, "username": "user7", "name": "club7", "avatar": 1},
            "club2": {"id": 8, "username": "user8", "name": "club8", "avatar": 1},
            "scheduledAt": "2026-01-01T18:00:00Z",
            "createdAt": "2025-12-31T18:00:00Z",
            "result": None,
            "playable": True,
        },
    }


@pytest.mark.parametrize("user_id, playable", [(7, True), (8, True), (9, False)])
def test_playable_only_for_the_two_clubs(user_id, playable):
    assert build_next_match_payload(state(), user_id)["match"]["playable"] is playable


def test_playable_while_the_match_is_being_played():
    started = match(1, 7, 8, status=MatchStatus.started)
    payload = build_next_match_payload(state(matches=[started]), 8)
    assert (payload["match"]["status"], payload["match"]["playable"]) == ("started", True)


@pytest.mark.parametrize("status", [LeagueStatus.finished, LeagueStatus.cancelled])
def test_finished_or_cancelled_league_has_no_match(status):
    payload = build_next_match_payload(state(status=status), 7)
    assert payload == {"type": "leagueNextMatch", "leagueStatus": status.value, "match": None}


def test_the_channel_closes_on_finished_and_cancelled():
    assert dict(NEXT_MATCH_CHANNEL.close_reasons) == {
        LeagueStatus.finished: "leagueFinished",
        LeagueStatus.cancelled: "leagueCancelled",
    }


# --- manager: un mensaje por conexión -----------------------------------------


class FakeWs:
    def __init__(self):
        self.received: list[dict] = []
        self.closed: tuple[int, str] | None = None

    async def send_text(self, text):
        self.received.append(json.loads(text))

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)


class HangingWs(FakeWs):
    """Cliente que no lee: el envío no termina nunca."""

    async def send_text(self, text):
        await asyncio.sleep(10)


@pytest.fixture()
def leagues():
    repo = FakeLeagues()
    repo.add(1, status=LeagueStatus.started)
    return repo


@pytest.fixture()
def fixtures(leagues):
    repo = FakeFixtures(leagues)
    repo.set(1, [match(11, CREATOR_ID, 8, 0), match(12, CREATOR_ID, 9, 1), match(13, 8, 9, 2)])
    return repo


@pytest.fixture()
def manager(fixtures):
    return LeagueNextMatchManager(fixtures.get_state)


def connect(manager, ws, user_id, league_id=1, session_id="s"):
    manager.reserve(league_id, user_id)
    connection = manager.subscribe(league_id, user_id, session_id, ws)
    return connection, asyncio.create_task(connection.run())


async def settle(seconds=0.1):
    await asyncio.sleep(seconds)


async def stop(*tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def seen(ws) -> list[tuple[int, bool]]:
    return [(m["match"]["id"], m["match"]["playable"]) for m in ws.received]


def test_each_connection_gets_its_own_playable(manager):
    club, rival, other = FakeWs(), FakeWs(), FakeWs()

    async def main():
        _, t1 = connect(manager, club, user_id=CREATOR_ID)
        _, t2 = connect(manager, rival, user_id=8)
        _, t3 = connect(manager, other, user_id=9)
        await settle()
        await stop(t1, t2, t3)

    asyncio.run(main())
    assert seen(club) == seen(rival) == [(11, True)]
    assert seen(other) == [(11, False)]


def test_playable_follows_the_new_next_match(manager, fixtures):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws, user_id=9)
        await settle()
        fixtures.update(1, 11, status=MatchStatus.finished, score_1=1, score_2=0)
        manager.next_match_changed(1)
        await settle()
        await stop(task)

    asyncio.run(main())
    assert seen(ws) == [(11, False), (12, True)]


def test_a_client_that_does_not_read_does_not_delay_the_notifier_nor_others(manager, fixtures):
    healthy = FakeWs()
    elapsed = {}

    async def main():
        _, t1 = connect(manager, HangingWs(), user_id=8)
        _, t2 = connect(manager, healthy, user_id=9)
        await settle()
        fixtures.update(1, 11, status=MatchStatus.started)

        def notify():
            began = time.perf_counter()
            manager.next_match_changed(1)
            elapsed["notify"] = time.perf_counter() - began

        await asyncio.to_thread(notify)
        await settle()
        await stop(t1, t2)

    asyncio.run(main())
    assert elapsed["notify"] < 0.05
    assert healthy.received[-1]["match"]["status"] == "started"


def test_the_finished_league_sends_null_and_closes_with_1000(manager, leagues, fixtures):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws, user_id=8)
        await settle()
        for match_id in (11, 12, 13):
            fixtures.update(1, match_id, status=MatchStatus.finished, score_1=1, score_2=0)
        leagues.set_status(1, LeagueStatus.finished)
        manager.next_match_changed(1)
        await settle()
        assert task.done()

    asyncio.run(main())
    assert ws.received[-1] == {"type": "leagueNextMatch", "leagueStatus": "finished", "match": None}
    assert ws.closed == (1000, "leagueFinished")
