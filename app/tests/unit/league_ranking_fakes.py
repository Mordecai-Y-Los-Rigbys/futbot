from app.repositories.ranking_abstract import ClubRankingData
from app.services.league_ranking_channel import LeagueRankingState
from app.tests.unit.league_participants_fakes import FakeLeagues


class FakeRankings:
    """Totales por liga, uno por participante."""

    def __init__(self, leagues: FakeLeagues):
        self.leagues = leagues
        self.clubs: dict[int, list[ClubRankingData]] = {}

    def set(self, league_id, clubs):
        self.clubs[league_id] = list(clubs)

    def update(self, league_id, club_id, **fields):
        self.clubs[league_id] = [
            c.model_copy(update=fields) if c.club_id == club_id else c
            for c in self.clubs[league_id]
        ]

    def get_state(self, league_id) -> LeagueRankingState | None:
        status = self.leagues.get_status(league_id)
        if status is None:
            return None
        return LeagueRankingState(status=status, clubs=list(self.clubs.get(league_id, [])))
