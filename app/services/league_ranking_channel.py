from collections.abc import Collection
from dataclasses import dataclass

from app.domain.league import LeagueStatus
from app.repositories.league_access_abstract import LeagueAccessRepository
from app.repositories.ranking_abstract import ClubRankingData
from app.services.league_channel_handshake import (
    LeagueChannelHandshakeService,
    LeagueStatusReader,
    ValidSessions,
)
from app.services.league_channel_manager import LeagueChannelManager, LeagueChannelSpec, LoadState
from app.services.league_fixture_channel import reject_unless_started
from app.services.ranking_service import to_league_ranking


@dataclass(frozen=True)
class LeagueRankingState:
    """Lo que se envía por /ws/leagues/{id}/ranking."""

    status: LeagueStatus
    clubs: list[ClubRankingData]  # uno por participante, sin orden


def build_ranking_payload(state: LeagueRankingState) -> dict:
    """Mensaje `leagueRanking` del AsyncAPI. Una liga cancelada no tiene ranking."""
    clubs = [] if state.status == LeagueStatus.cancelled else state.clubs
    return {
        "type": "leagueRanking",
        "leagueStatus": state.status.value,
        "ranking": [
            entry.model_dump(mode="json", by_alias=True) for entry in to_league_ranking(clubs)
        ],
    }


RANKING_CHANNEL = LeagueChannelSpec(
    build_payload=build_ranking_payload,
    close_reasons={
        LeagueStatus.finished: "leagueFinished",
        LeagueStatus.cancelled: "leagueCancelled",
    },
)


class LeagueRankingHandshakeService(LeagueChannelHandshakeService):
    """Valida el handshake de /ws/leagues/{id}/ranking: solo en started."""

    def __init__(
        self,
        allowed_origins: Collection[str],
        sessions: ValidSessions,
        access: LeagueAccessRepository,
        statuses: LeagueStatusReader,
    ) -> None:
        super().__init__(allowed_origins, sessions, access, statuses, reject_unless_started)


class LeagueRankingManager(LeagueChannelManager):
    """Conexiones a /ws/leagues/{id}/ranking."""

    def __init__(self, load_state: LoadState) -> None:
        super().__init__(load_state, RANKING_CHANNEL)

    def ranking_changed(self, league_id: int) -> None:
        """Terminó un partido de la liga o la liga se canceló. Llamar después del commit."""
        self.notify(league_id)