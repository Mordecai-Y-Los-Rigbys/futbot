from datetime import timedelta

from app.services.match_timing import (
    MAX_DURATION_TIMEDELTA,
    MAX_FRIENDLY_WAIT,
    MAX_PAUSES,
    WS_TOKEN_MARGIN,
    WS_TOKEN_TTL,
)


def test_ws_token_ttl_is_exactly_35_minutes():
    assert WS_TOKEN_TTL == timedelta(minutes=35)


def test_ws_token_ttl_covers_wait_match_pauses_and_margin():
    assert MAX_FRIENDLY_WAIT == timedelta(minutes=15)
    assert MAX_DURATION_TIMEDELTA == timedelta(minutes=10)
    assert MAX_PAUSES == timedelta(seconds=45)  # 3 pausas de 15 s
    assert WS_TOKEN_MARGIN == timedelta(minutes=9, seconds=15)
    assert WS_TOKEN_TTL == MAX_FRIENDLY_WAIT + MAX_DURATION_TIMEDELTA + MAX_PAUSES + WS_TOKEN_MARGIN