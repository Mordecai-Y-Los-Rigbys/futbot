import pytest
import asyncio

from app.errors import ApiError
from app.services.match_connection_manager import (
    MAX_CONNECTIONS_PER_USER_AND_MATCH,
    MatchConnectionManager,
)


@pytest.fixture()
def manager():
    return MatchConnectionManager()


def test_limit_is_five():
    assert MAX_CONNECTIONS_PER_USER_AND_MATCH == 5


def test_allows_up_to_five_connections_per_user_and_match(manager):
    for _ in range(5):
        manager.reserve(1, 7)
    assert manager.count(1, 7) == 5


def test_sixth_connection_is_429(manager):
    for _ in range(5):
        manager.reserve(1, 7)
    with pytest.raises(ApiError) as exc:
        manager.reserve(1, 7)
    assert (exc.value.status_code, exc.value.code) == (429, "tooManyConnections")
    assert manager.count(1, 7) == 5  # el rechazo no consume cupo


def test_limit_is_per_user(manager):
    for _ in range(5):
        manager.reserve(1, 7)
    manager.reserve(1, 8)  # otro usuario, mismo partido
    assert manager.count(1, 8) == 1


def test_limit_is_per_match(manager):
    for _ in range(5):
        manager.reserve(1, 7)
    manager.reserve(2, 7)  # mismo usuario, otro partido
    assert manager.count(2, 7) == 1


def test_releasing_a_connection_frees_a_slot(manager):
    sockets = [object() for _ in range(5)]
    for ws in sockets:
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    manager.release(1, 7, sockets[0])
    manager.reserve(1, 7)  # no debe lanzar

    assert manager.count(1, 7) == 5


def test_subscribers_are_listed_per_match(manager):
    a, b, c = object(), object(), object()
    for match_id, ws in [(1, a), (1, b), (2, c)]:
        manager.reserve(match_id, 7)
        manager.subscribe(match_id, 7, ws)

    assert set(manager.subscribers(1)) == {(a, 7), (b, 7)}
    assert manager.subscribers(2) == [(c, 7)]

def test_subscribers_carry_the_user_id(manager):
    a, b = object(), object()
    manager.reserve(1, 7); manager.subscribe(1, 7, a)
    manager.reserve(1, 8); manager.subscribe(1, 8, b)
    assert dict(manager.subscribers(1)) == {a: 7, b: 8}


def test_release_removes_the_subscriber(manager):
    a, b = object(), object()
    for ws in (a, b):
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    manager.release(1, 7, a)

    assert manager.subscribers(1) == [(b, 7)]
    assert manager.count(1, 7) == 1


def test_release_before_subscribe_still_frees_the_slot(manager):
    # el accept() falló antes de suscribir
    ws = object()
    manager.reserve(1, 7)
    manager.release(1, 7, ws)
    assert manager.count(1, 7) == 0


def test_release_leaves_no_residue(manager):
    ws = object()
    manager.reserve(1, 7)
    manager.subscribe(1, 7, ws)
    manager.release(1, 7, ws)

    assert manager.subscribers(1) == []
    assert manager._reserved == {} and manager._subscribers == {}


def test_double_release_does_not_go_negative(manager):
    ws = object()
    manager.reserve(1, 7)
    manager.subscribe(1, 7, ws)
    manager.release(1, 7, ws)
    manager.release(1, 7, ws)
    manager.reserve(1, 7)
    assert manager.count(1, 7) == 1


def test_subscribers_of_unknown_match_is_empty(manager):
    # Emitir a un partido sin nadie conectado no es un error.
    assert manager.subscribers(999) == []


class FakeWs:
    def __init__(self, fail=False):
        self.fail, self.closed = fail, None

    async def close(self, code=1000, reason=None):
        if self.fail:
            raise RuntimeError("ya cerrado")
        self.closed = (code, reason)


def test_close_match_closes_every_subscriber_even_if_one_fails(manager):
    broken, ok = FakeWs(fail=True), FakeWs()
    for ws in (broken, ok):
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    asyncio.run(manager.close_match(1))

    assert ok.closed == (1000, "waitExpired")


def test_close_match_without_subscribers_is_a_noop(manager):
    asyncio.run(manager.close_match(999))

def test_close_match_does_not_touch_other_matches(manager):
    mine, other = FakeWs(), FakeWs()
    manager.reserve(1, 7)
    manager.subscribe(1, 7, mine)
    manager.reserve(2, 7)
    manager.subscribe(2, 7, other)

    asyncio.run(manager.close_match(1))

    assert mine.closed == (1000, "waitExpired")
    assert other.closed is None  # el otro partido no se toca
    assert manager.subscribers(2) == [(other, 7)]

# --- evict ---------------------------------------------------------------------


def test_evict_frees_the_slot_and_the_subscription_immediately(manager):
    ws = object()
    manager.reserve(1, 7)
    manager.subscribe(1, 7, ws)

    manager.evict(1, 7, ws)

    assert manager.count(1, 7) == 0
    assert manager.subscribers(1) == []


def test_release_after_evict_does_not_free_another_connections_slot(manager):
    # Dos conexiones vivas del mismo usuario: si el release() del endpoint se
    # sumara al evict(), el cupo de la segunda se descontaría por error.
    a, b = object(), object()
    for ws in (a, b):
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    manager.evict(1, 7, a)
    manager.release(1, 7, a)  # el finally del endpoint

    assert manager.count(1, 7) == 1
    assert manager.subscribers(1) == [(b, 7)]


def test_evict_twice_is_idempotent(manager):
    a, b = object(), object()
    for ws in (a, b):
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    manager.evict(1, 7, a)
    manager.evict(1, 7, a)

    assert manager.count(1, 7) == 1


def test_evicted_slot_can_be_reused_right_away(manager):
    sockets = [object() for _ in range(5)]
    for ws in sockets:
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    manager.evict(1, 7, sockets[0])
    manager.reserve(1, 7)  # no debe lanzar 429

    assert manager.count(1, 7) == 5


def test_evict_then_release_leaves_no_residue(manager):
    ws = object()
    manager.reserve(1, 7)
    manager.subscribe(1, 7, ws)

    manager.evict(1, 7, ws)
    manager.release(1, 7, ws)

    assert manager._reserved == {} and manager._subscribers == {}
    assert manager._evicted == set()  # sin fuga de memoria

def test_evict_after_the_endpoint_already_released_is_a_noop(manager):
    a, b = object(), object()
    for ws in (a, b):
        manager.reserve(1, 7)
        manager.subscribe(1, 7, ws)

    manager.release(1, 7, a)   # el endpoint se adelantó
    manager.evict(1, 7, a)     # el broadcast llega tarde

    assert manager.count(1, 7) == 1
    assert manager.subscribers(1) == [(b, 7)]
    assert manager._evicted == set()  # sin fuga