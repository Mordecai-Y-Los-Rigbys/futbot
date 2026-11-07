from datetime import datetime

from starlette.websockets import WebSocket

from app.domain.league import LeagueStatus
from app.repositories.league_participants_abstract import LeagueParticipantsState
from app.services.league_channel_manager import (  # noqa: F401  (re-exportados)
    INTERNAL_ERROR_CODE,
    LEAGUE_CLOSED_CODE,
    LEAGUE_NOT_FOUND_CODE,
    LEAGUE_NOT_FOUND_REASON,
    MAX_CONNECTIONS_PER_USER_AND_LEAGUE,
    SESSION_ENDED_CODE,
    SESSION_ENDED_REASON,
    LeagueChannelConnection,
    LeagueChannelManager,
    LeagueChannelSpec,
    LoadState,
)

CLOSE_REASONS = {
    LeagueStatus.started: "leagueStarted",
    LeagueStatus.cancelled: "leagueCancelled",
    LeagueStatus.finished: "leagueFinished",
}


def build_participants_payload(state: LeagueParticipantsState) -> dict:
    """Mensaje `leagueParticipants` del AsyncAPI."""
    return {
        "type": "leagueParticipants",
        "leagueStatus": state.status.value,
        "participants": [
            {"id": p.id, "username": p.username, "name": p.club_name, "avatar": p.avatar}
            for p in state.participants
        ],
    }


PARTICIPANTS_CHANNEL = LeagueChannelSpec(
    build_payload=build_participants_payload,
    close_reasons=CLOSE_REASONS,
)


class ParticipantsConnection(LeagueChannelConnection):
    def __init__(
        self,
        league_id: int,
        user_id: int,
        session_id: str,
        websocket: WebSocket,
        load_state: LoadState,
        session_expires_at: datetime | None = None,
    ) -> None:
        super().__init__(
            league_id, user_id, session_id, websocket,
            load_state, PARTICIPANTS_CHANNEL, session_expires_at,
        )


class LeagueParticipantsManager(LeagueChannelManager):
    """Conexiones a /ws/leagues/{id}/participants. Implementa LeagueParticipantsNotifier."""

    def __init__(self, load_state: LoadState) -> None:
        super().__init__(load_state, PARTICIPANTS_CHANNEL)

    def _new_connection(self, league_id, user_id, session_id, websocket, session_expires_at):
        return ParticipantsConnection(
            league_id, user_id, session_id, websocket, self._load_state, session_expires_at
        )

    def participants_changed(self, league_id: int) -> None:
        """Alguien se unió o abandonó. Llamar después del commit."""
        self.notify(league_id)

    def league_status_changed(self, league_id: int) -> None:
        """La liga salió de `preparation`: último mensaje y cierre con 1000."""
        self.notify(league_id)