from datetime import datetime, timedelta, timezone

from app.domain.match import MatchStatus
from app.repositories.league_abstract import LeagueFixtureClubData, LeagueFixtureMatchData
from app.services.league_fixture_channel import LeagueFixtureState
from app.tests.unit.league_participants_fakes import FakeLeagues

START = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


def club(user_id: int) -> LeagueFixtureClubData:
    return LeagueFixtureClubData(
        id=user_id, username=f"user{user_id}", club_name=f"club{user_id}", avatar=1
    )


def match(match_id, user_1, user_2, hours=0, status=MatchStatus.scheduled, score=None):
    score_1, score_2 = score or (None, None)
    return LeagueFixtureMatchData(
        id=match_id,
        status=status,
        club_1=club(user_1),
        club_2=club(user_2),
        scheduled_at=START + timedelta(hours=hours),
        created_at=START - timedelta(days=1),
        score_1=score_1,
        score_2=score_2,
    )


class FakeFixtures:
    """Partidos por liga, en el orden en que se cargan (el repo real ordena)."""

    def __init__(self, leagues: FakeLeagues):
        self.leagues = leagues
        self.matches: dict[int, list[LeagueFixtureMatchData]] = {}

    def set(self, league_id, matches):
        self.matches[league_id] = list(matches)

    def update(self, league_id, match_id, **fields):
        self.matches[league_id] = [
            m.model_copy(update=fields) if m.id == match_id else m
            for m in self.matches[league_id]
        ]

    def get_state(self, league_id) -> LeagueFixtureState | None:
        status = self.leagues.get_status(league_id)
        if status is None:
            return None
        return LeagueFixtureState(
            league_id=league_id, status=status, matches=list(self.matches.get(league_id, []))
        )