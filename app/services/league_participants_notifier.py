from typing import Protocol


class LeagueParticipantsNotifier(Protocol):
    def participants_changed(self, league_id: int) -> None:
        """Emite la lista completa y actualizada en /ws/leagues/{id}/participants."""