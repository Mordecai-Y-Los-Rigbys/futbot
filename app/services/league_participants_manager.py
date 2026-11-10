from app.domain.league import LeagueStatus
from app.repositories.league_participants_abstract import LeagueParticipantsState
from app.services.league_channel_manager import LeagueChannelManager, LeagueChannelSpec, LoadState

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
    build_payload=lambda state, _user_id: build_participants_payload(state),
    close_reasons=CLOSE_REASONS,
)


class LeagueParticipantsManager(LeagueChannelManager):
    """Conexiones a /ws/leagues/{id}/participants. Implementa LeagueParticipantsNotifier."""

    def __init__(self, load_state: LoadState) -> None:
        super().__init__(load_state, PARTICIPANTS_CHANNEL)

    def participants_changed(self, league_id: int) -> None:
        """Alguien se unió o abandonó. Llamar después del commit."""
        self.notify(league_id)

    def league_status_changed(self, league_id: int) -> None:
        """La liga salió de `preparation`: último mensaje y cierre con 1000."""
        self.notify(league_id)
