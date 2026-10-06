import pytest

from app.errors import ApiError
from app.services.league_validation import MemberInput
from app.services.team_ownership import ensure_owned_team
from app.tests.unit.repo_fakes import FakeBehaviors, FakePlayers

MEMBERS = [MemberInput(player_id=i, behavior_id=10 + (i % 2), role="x") for i in range(1, 7)]


def test_owned_team_passes():
    ensure_owned_team(FakePlayers(), FakeBehaviors(), 1, MEMBERS)


@pytest.mark.parametrize(
    "players, behaviors",
    [
        (FakePlayers(owned={1, 2, 3, 4, 5}), FakeBehaviors()),  # falta el jugador 6
        (FakePlayers(), FakeBehaviors(owned={10})),  # falta el behavior 11
        (FakePlayers(owned=set()), FakeBehaviors(owned=set())),
    ],
)
def test_missing_or_foreign_ids_are_409(players, behaviors):
    with pytest.raises(ApiError) as e:
        ensure_owned_team(players, behaviors, 1, MEMBERS)
    assert (e.value.status_code, e.value.code) == (409, "playerOrBehaviorNotOwned")


def test_repeated_behavior_is_queried_once():
    seen = []

    class Spy(FakeBehaviors):
        def owned_behavior_ids(self, user_id, ids):
            seen.append(sorted(ids))
            return super().owned_behavior_ids(user_id, ids)

    ensure_owned_team(FakePlayers(), Spy(), 1, MEMBERS)
    assert seen == [[10, 11]]
