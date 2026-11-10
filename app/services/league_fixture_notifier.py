from typing import Protocol


class LeagueFixtureNotifier(Protocol):
    def fixture_changed(self, league_id: int) -> None:
        """Emite el fixture completo y actualizado en /ws/leagues/{id}/fixture."""
