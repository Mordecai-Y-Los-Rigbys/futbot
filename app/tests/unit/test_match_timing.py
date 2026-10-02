from datetime import timedelta
from pathlib import Path

import pytest

from app.services.match_timing import (
    MAX_FRIENDLY_WAIT,
    MAX_MATCH_DURATION,
    WS_TOKEN_MARGIN,
    WS_TOKEN_TTL,
)
from app.startup_checks import ensure_single_worker


def test_ws_token_ttl_covers_wait_match_and_margin():
    assert WS_TOKEN_TTL >= MAX_FRIENDLY_WAIT + MAX_MATCH_DURATION + WS_TOKEN_MARGIN


@pytest.mark.parametrize("value", ["2", "10"])
def test_more_than_one_worker_aborts_startup(value):
    with pytest.raises(RuntimeError, match="1 worker"):
        ensure_single_worker({"WEB_CONCURRENCY": value})


@pytest.mark.parametrize("env", [{}, {"WEB_CONCURRENCY": "1"}, {"WEB_CONCURRENCY": "abc"}])
def test_one_worker_or_unset_does_not_abort(env):
    ensure_single_worker(env)

COMPOSE = Path(__file__).parents[3] / "docker-compose.yml"


@pytest.mark.skipif(not COMPOSE.exists(), reason="docker-compose.yml no está disponible")
def test_start_command_has_no_workers_flag_and_sets_ws_ping():
    text = COMPOSE.read_text()
    assert "--workers" not in text
    assert "--ws-ping-interval" in text
    assert "--ws-ping-timeout" in text