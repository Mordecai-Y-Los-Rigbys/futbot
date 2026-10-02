from datetime import datetime, timedelta, timezone

from app.repositories.match_abstract import AbstractMatchRepository, MatchStateData
from app.repositories.match_ws_token_abstract import (
    AbstractMatchWsTokenRepository,
    MatchWsTokenData,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


class FakeTokenRepo(AbstractMatchWsTokenRepository):
    def __init__(self):
        self.tokens: dict[str, MatchWsTokenData] = {}
        self.lookups: list[str] = []

    def add(self, token="tok", user_id=7, match_id=1, expires_at=None):
        self.tokens[token] = MatchWsTokenData(
            token=token,
            user_id=user_id,
            match_id=match_id,
            expires_at=expires_at or NOW + timedelta(hours=1),
        )

    def get_by_token(self, token):
        self.lookups.append(token)
        return self.tokens.get(token)


class FakeMatchRepo(AbstractMatchRepository):
    def __init__(self):
        self.states: dict[int, MatchStateData] = {}

    def add(self, match_id=1, finished=False):
        self.states[match_id] = MatchStateData(id=match_id, finished=finished)

    def get_state(self, match_id):
        return self.states.get(match_id)