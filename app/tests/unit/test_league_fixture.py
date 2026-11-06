import random
from datetime import datetime, timedelta, timezone
from itertools import combinations

import pytest

from app.services.league_fixture import build_fixture, match_slot

START = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)
SLOT = timedelta(minutes=7, seconds=5)


def fixture(ids, seed=1, slot=SLOT):
    return build_fixture(ids, START, slot, random.Random(seed))


def pairs(matches):
    return [(m.user_1_id, m.user_2_id) for m in matches]


@pytest.mark.parametrize("n", [2, 3, 4, 5, 8])
def test_one_match_per_pair(n):
    ids = [10 * i for i in range(1, n + 1)]
    matches = fixture(ids)
    assert len(matches) == n * (n - 1) // 2
    assert {frozenset(p) for p in pairs(matches)} == {frozenset(p) for p in combinations(ids, 2)}
    

def test_the_input_order_does_not_change_the_result():
    assert pairs(fixture([4, 1, 3, 2], seed=7)) == pairs(fixture([1, 2, 3, 4], seed=7))
    

def test_order_depends_on_the_seed():
    ids = [1, 2, 3, 4, 5]
    orders = {tuple(pairs(fixture(ids, seed=s))) for s in range(5)}
    assert len(orders) > 1
    

def test_first_match_one_minute_after_the_start():
    assert fixture([1, 2, 3])[0].scheduled_at == START + timedelta(minutes=1)


def test_each_match_starts_one_slot_after_the_previous():
    times = [m.scheduled_at for m in fixture([1, 2, 3, 4])]
    assert [b - a for a, b in zip(times, times[1:])] == [SLOT] * 5
    

def test_slot_in_normal_mode():
    # 5 min de juego + 65 s de pausas y countdowns + 1 min de margen
    assert match_slot(5, allow_draws=True) == timedelta(minutes=7, seconds=5)


def test_slot_in_penalties_mode_adds_the_shootout():
    assert match_slot(5, allow_draws=False) == timedelta(minutes=8, seconds=10)
    

@pytest.mark.parametrize("duration", [1, 10])
def test_slot_uses_the_league_duration(duration):
    assert match_slot(duration, True) - match_slot(1, True) == timedelta(minutes=duration - 1)
