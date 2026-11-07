from collections.abc import Collection
from dataclasses import dataclass

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.repositories.league_abstract import LeagueFixtureMatchData
from app.repositories.league_access_abstract import LeagueAccessRepository
from app.services.league_channel_handshake import (
    LeagueChannelHandshakeService,
    LeagueStatusReader,
    ValidSessions,
)
from app.services.league_channel_manager import LeagueChannelManager, LeagueChannelSpec, LoadState
from app.services.league_service import to_fixture_match


@dataclass(frozen=True)
class LeagueFixtureState:
    """Lo que se envía por /ws/leagues/{id}/fixture."""

    league_id: int
    status: LeagueStatus
    matches: list[LeagueFixtureMatchData]  # por scheduled_at y después id


def build_fixture_payload(state: LeagueFixtureState) -> dict:
    """Mensaje `leagueFixture` del AsyncAPI. Una liga cancelada no tiene fixture."""
    matches = [] if state.status == LeagueStatus.cancelled else state.matches
    return {
        "type": "leagueFixture",
        "leagueStatus": state.status.value,
        "fixture": [
            to_fixture_match(state.league_id, m).model_dump(mode="json", by_alias=True)
            for m in matches
        ],
    }


FIXTURE_CHANNEL = LeagueChannelSpec(
    build_payload=build_fixture_payload,
    close_reasons={
        LeagueStatus.finished: "leagueFinished",
        LeagueStatus.cancelled: "leagueCancelled",
    },
)

_NOT_STARTED_REASONS = {
    LeagueStatus.preparation: "leagueNotStarted",
    LeagueStatus.finished: "leagueFinished",
    LeagueStatus.cancelled: "leagueCancelled",
}


def reject_unless_started(status: LeagueStatus | None) -> ApiError | None:
    if status == LeagueStatus.started:
        return None
    reason = _NOT_STARTED_REASONS.get(status, "leagueNotStarted")
    return ApiError(409, reason, "La liga no está en curso.")


class LeagueFixtureHandshakeService(LeagueChannelHandshakeService):
    """Valida el handshake de /ws/leagues/{id}/fixture: solo en started."""

    def __init__(
        self,
        allowed_origins: Collection[str],
        sessions: ValidSessions,
        access: LeagueAccessRepository,
        statuses: LeagueStatusReader,
    ) -> None:
        super().__init__(allowed_origins, sessions, access, statuses, reject_unless_started)


class LeagueFixtureManager(LeagueChannelManager):
    """Conexiones a /ws/leagues/{id}/fixture. Implementa LeagueFixtureNotifier."""

    def __init__(self, load_state: LoadState) -> None:
        super().__init__(load_state, FIXTURE_CHANNEL)

    def fixture_changed(self, league_id: int) -> None:
        """Un partido empezó o terminó, o la liga cambió de estado. Llamar después del commit."""
        self.notify(league_id)