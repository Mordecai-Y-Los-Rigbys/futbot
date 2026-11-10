from collections.abc import Iterable

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.repositories.league_abstract import LeagueFixtureMatchData
from app.services.league_channel_manager import LeagueChannelManager, LeagueChannelSpec, LoadState
from app.services.league_fixture_channel import LeagueFixtureHandshakeService, LeagueFixtureState
from app.services.league_service import to_fixture_match


def pick_next_match(matches: Iterable[LeagueFixtureMatchData]) -> LeagueFixtureMatchData | None:
    """El partido en `started`; si no hay, el primer `scheduled` por scheduled_at y después id."""
    pending = [m for m in matches if m.status in (MatchStatus.started, MatchStatus.scheduled)]
    return min(
        pending,
        key=lambda m: (m.status != MatchStatus.started, m.scheduled_at, m.id),
        default=None,
    )


def build_next_match_payload(state: LeagueFixtureState, user_id: int) -> dict:
    """Mensaje `leagueNextMatch` del AsyncAPI. `match` es null solo con la liga terminada o cancelada."""
    next_match = pick_next_match(state.matches) if state.status == LeagueStatus.started else None
    match = None
    if next_match is not None:
        match = to_fixture_match(state.league_id, next_match).model_dump(mode="json", by_alias=True)
        match["playable"] = user_id in (next_match.club_1.id, next_match.club_2.id)
    return {"type": "leagueNextMatch", "leagueStatus": state.status.value, "match": match}


NEXT_MATCH_CHANNEL = LeagueChannelSpec(
    build_payload=build_next_match_payload,
    close_reasons={
        LeagueStatus.finished: "leagueFinished",
        LeagueStatus.cancelled: "leagueCancelled",
    },
)


class LeagueNextMatchHandshakeService(LeagueFixtureHandshakeService):
    """Valida el handshake de /ws/leagues/{id}/matches/next: igual que el fixture, solo en started."""


class LeagueNextMatchManager(LeagueChannelManager):
    """Conexiones a /ws/leagues/{id}/matches/next. Cada conexión arma su propio mensaje."""

    def __init__(self, load_state: LoadState) -> None:
        super().__init__(load_state, NEXT_MATCH_CHANNEL)

    def next_match_changed(self, league_id: int) -> None:
        """Un partido empezó o terminó, o la liga cambió de estado. Llamar después del commit."""
        self.notify(league_id)
