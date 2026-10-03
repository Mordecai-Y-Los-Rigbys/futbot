from app.repositories.team_abstract import AbstractTeamRepository


class FakeTeams(AbstractTeamRepository):
    """Por defecto, todo id pertenece al usuario. Configurable por test."""

    def __init__(self, starters=None, owned_players=None, owned_behaviors=None):
        self.starters = starters or {}      # {user_id: [StarterData]}
        self.owned_players = owned_players  # None = todos son del usuario
        self.owned_behaviors = owned_behaviors
        self.calls = []

    def get_starters(self, match_id, league_id, user_id):
        self.calls.append((match_id, league_id, user_id))
        return self.starters.get(user_id, [])

    def owned_player_ids(self, user_id, ids):
        return set(ids) if self.owned_players is None else set(ids) & self.owned_players

    def owned_behavior_ids(self, user_id, ids):
        return set(ids) if self.owned_behaviors is None else set(ids) & self.owned_behaviors