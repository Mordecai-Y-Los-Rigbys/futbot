"""Armado de los clubes de la prueba a partir de la alineación del token."""

from app.domain.team_member import MemberRole
from app.repositories.team_abstract import StarterData
from app.services import behavior_test_handshake
from app.services.behavior_test_handshake import BehaviorTestHandshakeService
from app.tests.unit.behavior_test_fakes import (
    NOW,
    OTHER_ID,
    TESTED_ID,
    USER_ID,
    FakeLineupRepo,
    FakeTestTokenRepo,
)


def test_each_club_gets_its_players_with_their_stats_role_and_behavior(monkeypatch):
    monkeypatch.setattr(behavior_test_handshake, "_utcnow", lambda: NOW)
    tokens, lineups = FakeTestTokenRepo(), FakeLineupRepo()
    tokens.add()
    lineups.codes = {TESTED_ID: "pass", OTHER_ID: "go_to(0, 0)"}

    grant = BehaviorTestHandshakeService(tokens, lineups).authorize("tok", str(TESTED_ID))

    def starter(player_id, role, code):
        return StarterData(
            player_id=player_id,
            name=f"Jugador {player_id}",
            role=role,
            power=50 + player_id,
            agility=60,
            control=60,
            strength=60,
            speed=70 - player_id,
            behavior_code=code,
        )

    assert (grant.user_id, grant.behavior_id) == (USER_ID, TESTED_ID)
    assert grant.club_1 == [
        starter(1, MemberRole.forward, "pass"),
        starter(2, MemberRole.midfield, "pass"),
        starter(3, MemberRole.defense, "pass"),
    ]
    assert grant.club_2 == [
        starter(4, MemberRole.forward, "go_to(0, 0)"),
        starter(5, MemberRole.midfield, "pass"),
        starter(6, MemberRole.defense, "pass"),
    ]
