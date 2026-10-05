from datetime import datetime, timedelta, timezone

from app.models.match import MatchStatus
from app.repositories.match_abstract import (
    AbstractMatchRepository, 
    MatchSetupData,
    MatchStateData
)
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
        self.setups: dict[int, MatchSetupData] = {}
        self.results: dict[int, tuple[int, int]] = {}
        self.history: list[str] = []
        self.seeds: dict[int, int] = {}

    def add(self, match_id=1, status=MatchStatus.scheduled):
        self.states[match_id] = MatchStateData(
            id=match_id, status=MatchStatus(status).value
        )

    def get_state(self, match_id):
        return self.states.get(match_id)

    def get_setup_data(self, match_id: int) -> MatchSetupData | None:
        return self.setups.get(match_id)

    def mark_started(self, match_id: int) -> None:
        self.history.append("started")
        self._set_status(match_id, MatchStatus.started)

    def finish(self, match_id: int, score_1: int, score_2: int) -> None:
        self.history.append("finished")
        self.results[match_id] = (score_1, score_2)
        self._set_status(match_id, MatchStatus.finished)

    def _set_status(self, match_id: int, status: MatchStatus) -> None:
        # Algunos tests no llaman a add(): en ese caso solo se registra el historial.
        if match_id in self.states:
            self.states[match_id] = MatchStateData(id=match_id, status=status.value)
    
    def save_seed(self, match_id, seed):
        self.seeds[match_id] = seed