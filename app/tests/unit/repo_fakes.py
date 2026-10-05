from app.repositories.team_abstract import AbstractTeamRepository


class FakeTeams(AbstractTeamRepository):
    def __init__(self, starters=None):
        self.starters = starters or {}
        self.calls = []

    def get_starters(self, match_id, league_id, user_id):
        self.calls.append((match_id, league_id, user_id))
        return self.starters.get(user_id, [])

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