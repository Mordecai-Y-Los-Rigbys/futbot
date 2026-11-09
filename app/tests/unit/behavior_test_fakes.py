"""Fakes del WebSocket de la prueba de un comportamiento."""

from datetime import datetime, timedelta, timezone

from app.domain.team_member import MemberRole
from app.repositories.behavior_test_lineup_abstract import AbstractBehaviorTestLineupRepository
from app.repositories.behavior_test_token_abstract import (
    AbstractBehaviorTestTokenRepository,
    BehaviorTestMemberData,
    BehaviorTestTokenData,
)
from app.repositories.player_abstract import PlayerData

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
USER_ID = 7
TESTED_ID = 5  # el behavior que se prueba
OTHER_ID = 6  # otro behavior de la alineación
IDLE = "pass"

# (player_id, club, rol, behavior): el jugador 4 juega con el otro behavior.
LINEUP = [
    (1, "club1", MemberRole.forward, TESTED_ID),
    (2, "club1", MemberRole.midfield, TESTED_ID),
    (3, "club1", MemberRole.defense, TESTED_ID),
    (4, "club2", MemberRole.forward, OTHER_ID),
    (5, "club2", MemberRole.midfield, TESTED_ID),
    (6, "club2", MemberRole.defense, TESTED_ID),
]


def lineup_members(lineup=LINEUP) -> list[BehaviorTestMemberData]:
    return [
        BehaviorTestMemberData(player_id=player_id, club=club, role=role, behavior_id=behavior_id)
        for player_id, club, role, behavior_id in lineup
    ]


class FakeTestTokenRepo(AbstractBehaviorTestTokenRepository):
    def __init__(self):
        self.tokens: dict[str, BehaviorTestTokenData] = {}

    def add(self, token="tok", behavior_id=TESTED_ID, expires_at=None, members=None):
        self.tokens[token] = BehaviorTestTokenData(
            token=token,
            user_id=USER_ID,
            behavior_id=behavior_id,
            expires_at=expires_at or NOW + timedelta(minutes=5),
            members=members or lineup_members(),
        )

    def create(self, data):
        raise NotImplementedError

    def get_by_token(self, token):
        return self.tokens.get(token)


class FakeLineupRepo(AbstractBehaviorTestLineupRepository):
    def __init__(self):
        self.codes = {TESTED_ID: IDLE, OTHER_ID: IDLE}
        self.player_rows = {
            player_id: PlayerData(
                id=player_id,
                user_id=USER_ID,
                name=f"Jugador {player_id}",
                power=50 + player_id,
                agility=60,
                control=60,
                strength=60,
                speed=70 - player_id,
            )
            for player_id in range(1, 7)
        }

    def behavior_codes(self, user_id, ids):
        return {
            behavior_id: code
            for behavior_id, code in self.codes.items()
            if user_id == USER_ID and behavior_id in ids
        }

    def players(self, user_id, ids):
        return {
            player_id: player
            for player_id, player in self.player_rows.items()
            if player.user_id == user_id and player_id in ids
        }
