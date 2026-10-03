from datetime import timedelta
from app.services.match_timing import WS_TOKEN_TTL


def test_ws_token_ttl_covers_wait_match_and_margin():
    assert WS_TOKEN_TTL >= timedelta(minutes=35)