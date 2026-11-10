from app.repositories.team_abstract import AbstractTeamRepository
from app.domain.league import LeagueStatus
from app.repositories.ranking_abstract import AbstractRankingRepository, ClubRankingData


class FakeTeams(AbstractTeamRepository):
    def __init__(self, starters=None):
        self.starters = starters or {}
        self.calls = []

    def get_starters(self, match_id, league_id, user_id):
        self.calls.append((match_id, league_id, user_id))
        return self.starters.get(user_id, [])

    def get_lineup(self, match_id, league_id, user_id):
        raise NotImplementedError

    def set_behavior(self, match_id, league_id, player_id, behavior_id):
        raise NotImplementedError

    def get_team_player_ids(self, match_id, league_id, user_id, *, substitutes):
        raise NotImplementedError

    def get_member_id(self, match_id, league_id, user_id, player_id):
        raise NotImplementedError


class FakeRankingRepo(AbstractRankingRepository):
    def __init__(self, clubs=None, status=LeagueStatus.started):
        self.clubs = clubs or []
        self.status = status

    def list_club_totals(self):
        return list(self.clubs)

    def list_league_club_totals(self, league_id):
        return list(self.clubs)

    def get_league_status(self, league_id):
        return self.status


def ranking_club(id, name=None, wr=0, wp=0, d=0, l=0, gf=0, ga=0, avatar=1):
    return ClubRankingData(
        club_id=id,
        name=name or f"Club {id}",
        avatar=avatar,
        won_regular=wr,
        won_penalties=wp,
        drawn=d,
        lost=l,
        goals_for=gf,
        goals_against=ga,
    )


class FakePlayers:
    """Por defecto, todo id pertenece al usuario. `owned` lo restringe."""

    def __init__(self, owned=None):
        self.owned = owned  # None = todos son del usuario

    def owned_player_ids(self, user_id, ids):
        return set(ids) if self.owned is None else set(ids) & self.owned


class FakeBehaviors:
    def __init__(self, owned=None):
        self.owned = owned

    def owned_behavior_ids(self, user_id, ids):
        return set(ids) if self.owned is None else set(ids) & self.owned
