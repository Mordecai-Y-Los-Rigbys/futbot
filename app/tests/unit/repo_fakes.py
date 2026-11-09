from app.repositories.league_abstract import AbstractLeagueRepository
from app.repositories.team_abstract import AbstractTeamRepository


class FakeTeams(AbstractTeamRepository):
    def __init__(self, starters=None):
        self.starters = starters or {}
        self.calls = []

    def get_team_player_ids(self, match_id, league_id, user_id, *, substitutes):
        return set()

    def get_member_id(self, match_id, league_id, user_id, player_id):
        return None

    def get_starters(self, match_id, league_id, user_id):
        self.calls.append((match_id, league_id, user_id))
        return self.starters.get(user_id, [])

    def set_behavior(self, match_id, league_id, player_id, behavior_id):
        raise NotImplementedError


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

class FakeLeagues(AbstractLeagueRepository):
    def __init__(self, durations=None):
        self.durations = durations or {}
        self.calls = []

    def get_match_duration_minutes(self, league_id):
        self.calls.append(league_id)
        return self.durations.get(league_id)

    def list_page(self, name, offset, limit):
        raise NotImplementedError

    def create(self, data):
        raise NotImplementedError
    
    def get_detail(self, league_id: int, user_id: int):
        raise NotImplementedError

    def get_leave_info(self, league_id):
        raise NotImplementedError

    def is_participant(self, league_id, user_id):
        raise NotImplementedError

    def remove_participant(self, league_id, user_id):
        raise NotImplementedError

    def get_join_state(self, league_id, user_id):
        raise NotImplementedError

    def join(self, data):
        raise NotImplementedError
    
    def get_start_state(self, data):
        raise NotImplementedError
    
    def list_participants(self, data):
        raise NotImplementedError
    
    def start(self, data):
        raise NotImplementedError
