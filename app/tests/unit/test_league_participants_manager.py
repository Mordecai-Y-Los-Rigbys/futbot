import asyncio
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.repositories.league_participants_abstract import LeagueParticipantsState, ParticipantData
from app.services.league_participants_manager import (
    LeagueParticipantsManager,
    build_participants_payload,
)
from app.tests.unit.league_participants_fakes import CREATOR_ID, FakeLeagues


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


class BrokenWs(FakeWs):
    async def send_text(self, text):
        raise RuntimeError("socket cerrado")


@pytest.fixture()
def leagues():
    repo = FakeLeagues()
    repo.add(1)
    repo.add(2)
    return repo


@pytest.fixture()
def manager(leagues):
    return LeagueParticipantsManager(leagues.get_state)


async def settle(seconds=0.1):
    await asyncio.sleep(seconds)


def ids(message) -> list[int]:
    return [p["id"] for p in message["participants"]]


def connect(manager, ws, league_id=1, user_id=8, session_id="s", expires_at=None):
    """Reserva, suscribe y arranca la tarea de envío, como el endpoint."""
    manager.reserve(league_id, user_id)
    connection = manager.subscribe(league_id, user_id, session_id, ws, expires_at)
    return connection, asyncio.create_task(connection.run())


async def stop(*tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


# --- payload ------------------------------------------------------------------


def test_payload_has_the_contract_shape():
    state = LeagueParticipantsState(
        status=LeagueStatus.preparation,
        participants=[ParticipantData(id=7, username="mgonzalez", club_name="Boca FC", avatar=3)],
    )
    assert build_participants_payload(state) == {
        "type": "leagueParticipants",
        "leagueStatus": "preparation",
        "participants": [{"id": 7, "username": "mgonzalez", "name": "Boca FC", "avatar": 3}],
    }


# --- límite de conexiones -----------------------------------------------------


def test_allows_up_to_five_connections_per_user_and_league(manager):
    for _ in range(5):
        manager.reserve(1, 8)
    assert manager.count(1, 8) == 5


def test_sixth_connection_is_429_and_does_not_take_a_slot(manager):
    for _ in range(5):
        manager.reserve(1, 8)
    with pytest.raises(ApiError) as exc:
        manager.reserve(1, 8)
    assert (exc.value.status_code, exc.value.code) == (429, "tooManyConnections")
    assert manager.count(1, 8) == 5


def test_limit_is_per_user_and_per_league(manager):
    for _ in range(5):
        manager.reserve(1, 8)
    manager.reserve(1, 9)  # otro usuario
    manager.reserve(2, 8)  # otra liga
    assert manager.count(1, 9) == 1 and manager.count(2, 8) == 1


def test_release_before_subscribe_frees_the_slot(manager):
    manager.reserve(1, 8)
    manager.release(1, 8)  # el accept falló
    assert manager.count(1, 8) == 0


def test_release_removes_the_subscriber_and_leaves_no_residue(manager):
    async def main():
        connection, task = connect(manager, FakeWs())
        await stop(task)
        manager.release(1, 8, connection)

    asyncio.run(main())
    assert manager.subscribers(1) == []
    assert manager._reserved == {} and manager._subscribers == {}


# --- mensaje inicial ----------------------------------------------------------


def test_on_connect_sends_the_current_state(manager):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws)
        await settle()
        await stop(task)

    asyncio.run(main())
    assert ws.received == [
        {
            "type": "leagueParticipants",
            "leagueStatus": "preparation",
            "participants": [{"id": CREATOR_ID, "username": "user7", "name": "club7", "avatar": 1}],
        }
    ]
    assert ws.closed is None


def test_state_is_read_after_subscribing_so_a_change_in_between_is_not_lost(manager, leagues):
    ws = FakeWs()

    async def main():
        manager.reserve(1, 8)
        connection = manager.subscribe(1, 8, "s", ws)
        # Alguien se une entre la suscripción y la primera lectura
        leagues.join(1, 9)
        manager.participants_changed(1)
        task = asyncio.create_task(connection.run())
        await settle()
        await stop(task)

    asyncio.run(main())
    assert ids(ws.received[-1]) == [CREATOR_ID, 9]


# --- cambios ------------------------------------------------------------------


def test_join_and_leave_send_the_full_updated_list(manager, leagues):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws)
        await settle()
        leagues.join(1, 9)
        manager.participants_changed(1)
        await settle()
        leagues.join(1, 10)
        manager.participants_changed(1)
        await settle()
        leagues.leave(1, 9)
        manager.participants_changed(1)
        await settle()
        await stop(task)

    asyncio.run(main())
    assert [ids(m) for m in ws.received] == [[7], [7, 9], [7, 9, 10], [7, 10]]
    assert all(m["leagueStatus"] == "preparation" for m in ws.received)


def test_every_connection_of_the_league_receives_the_change(manager, leagues):
    a, b = FakeWs(), FakeWs()

    async def main():
        _, ta = connect(manager, a, user_id=8)
        _, tb = connect(manager, b, user_id=9)
        await settle()
        leagues.join(1, 9)
        manager.participants_changed(1)
        await settle()
        await stop(ta, tb)

    asyncio.run(main())
    assert ids(a.received[-1]) == ids(b.received[-1]) == [7, 9]


def test_changes_of_one_league_do_not_reach_another(manager, leagues):
    mine, other = FakeWs(), FakeWs()

    async def main():
        _, t1 = connect(manager, mine, league_id=1)
        _, t2 = connect(manager, other, league_id=2)
        await settle()
        leagues.join(1, 9)
        manager.participants_changed(1)
        await settle()
        await stop(t1, t2)

    asyncio.run(main())
    assert len(mine.received) == 2
    assert len(other.received) == 1  # solo el inicial


def test_change_without_subscribers_is_a_noop(manager):
    manager.participants_changed(999)  # no lanza
    manager.session_ended("nadie")


def test_several_changes_in_a_row_end_with_the_latest_state(manager, leagues):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws)
        await settle()
        for uid in (9, 10, 11):
            leagues.join(1, uid)
            manager.participants_changed(1)
        await settle()
        await stop(task)

    asyncio.run(main())
    assert ids(ws.received[-1]) == [7, 9, 10, 11]
    assert len(ws.received) <= 4  # los avisos seguidos se pueden juntar en uno


def test_notifying_from_another_thread_works(manager, leagues):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws)
        await settle()
        leagues.join(1, 9)
        thread = threading.Thread(target=manager.participants_changed, args=(1,))
        thread.start()
        thread.join()
        await settle()
        await stop(task)

    asyncio.run(main())
    assert ids(ws.received[-1]) == [7, 9]


# --- cliente lento o caído ----------------------------------------------------


def test_a_client_that_does_not_read_does_not_delay_the_notifier_nor_others(manager, leagues):
    healthy = FakeWs()
    elapsed = {}

    async def main():
        _, t1 = connect(manager, HangingWs(), user_id=8)
        _, t2 = connect(manager, healthy, user_id=9)
        await settle()
        leagues.join(1, 10)

        def notify():
            began = time.perf_counter()
            manager.participants_changed(1)
            elapsed["notify"] = time.perf_counter() - began

        await asyncio.to_thread(notify)
        await settle()
        await stop(t1, t2)

    asyncio.run(main())
    assert elapsed["notify"] < 0.05
    assert ids(healthy.received[-1]) == [7, 10]


def test_a_broken_client_ends_its_task_without_raising(manager):
    ws = BrokenWs()

    async def main():
        _, task = connect(manager, ws)
        await settle()
        assert task.done() and task.exception() is None

    asyncio.run(main())


# --- fin de la liga -----------------------------------------------------------


@pytest.mark.parametrize(
    "status, reason",
    [
        (LeagueStatus.started, "leagueStarted"),
        (LeagueStatus.cancelled, "leagueCancelled"),
        (LeagueStatus.finished, "leagueFinished"),
    ],
)
def test_leaving_preparation_sends_a_last_message_and_closes_with_1000(
    manager, leagues, status, reason
):
    ws = FakeWs()

    async def main():
        _, task = connect(manager, ws)
        await settle()
        leagues.set_status(1, status)
        manager.league_status_changed(1)
        await settle()
        assert task.done()
        # Un aviso posterior ya no manda nada
        manager.participants_changed(1)
        await settle()

    asyncio.run(main())
    assert [m["leagueStatus"] for m in ws.received] == ["preparation", status.value]
    assert ids(ws.received[-1]) == [CREATOR_ID]
    assert ws.closed == (1000, reason)


# --- sesión -------------------------------------------------------------------


def test_session_ended_closes_its_connections_with_4401(manager):
    mine, other = FakeWs(), FakeWs()

    async def main():
        _, t1 = connect(manager, mine, session_id="s1")
        _, t2 = connect(manager, other, session_id="s2", user_id=9)
        await settle()
        manager.session_ended("s1")
        await settle()
        await stop(t1, t2)

    asyncio.run(main())
    assert mine.closed == (4401, "sessionEnded")
    assert len(mine.received) == 1  # sin mensaje extra antes del cierre
    assert other.closed is None


def test_session_expiry_closes_the_connection_with_4401(manager):
    ws = FakeWs()
    expires = datetime.now(timezone.utc) + timedelta(milliseconds=150)

    async def main():
        _, task = connect(manager, ws, expires_at=expires)
        await settle(0.4)
        await stop(task)

    asyncio.run(main())
    assert len(ws.received) == 1
    assert ws.closed == (4401, "sessionEnded")


def test_leaving_the_league_does_not_close_the_connection(manager, leagues):
    ws = FakeWs()
    leagues.join(1, 8)

    async def main():
        _, task = connect(manager, ws, user_id=8)
        await settle()
        leagues.leave(1, 8)
        manager.participants_changed(1)
        await settle()
        assert not task.done()
        await stop(task)

    asyncio.run(main())
    assert ids(ws.received[-1]) == [CREATOR_ID]
    assert ws.closed is None
