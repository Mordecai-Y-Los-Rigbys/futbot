from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.errors import ApiError
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    FriendlyClubData,
    FriendlyMatchData,
)
from app.services.friendly_service import FriendlyService

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]
NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


def body():
    return {
        "name": "Partido amistoso 1",
        "members": [
            {"playerId": i + 1, "role": r, "behaviorId": 10 + i}
            for i, r in enumerate(ROLES)
        ],
    }


@pytest.fixture()
def repo():
    r = MagicMock(spec=AbstractFriendlyRepository)
    r.user_is_playing.return_value = False
    r.owned_player_ids.side_effect = lambda uid, ids: set(ids)
    r.owned_behavior_ids.side_effect = lambda uid, ids: set(ids)
    r.create_with_team.return_value = FriendlyMatchData(
        id=100, name="Partido amistoso 1", status="scheduled",
        club1=FriendlyClubData(id=1, username="usuario1", club_name="Club Atletico"),
        created_at=NOW,
    )
    return r


def test_success_returns_the_match_schema(repo):
    out = FriendlyService(repo).create_friendly(1, body())
    dumped = out.model_dump(by_alias=True)
    assert dumped["id"] == 100 and dumped["status"] == "scheduled"
    assert dumped["club1"] == {"id": 1, "username": "usuario1", "name": "Club Atletico"}
    for k in ("leagueId", "club2", "scheduledAt", "result"):
        assert dumped[k] is None
    assert out.model_dump_json(by_alias=True).count("2026-10-03T18:00:00Z") == 1


def test_success_persists_the_creator_team(repo):
    FriendlyService(repo).create_friendly(1, body())
    data = repo.create_with_team.call_args.args[0]
    assert data.creator_id == 1 and data.name == "Partido amistoso 1"
    assert [(m.player_id, m.behavior_id, m.role) for m in data.members] == [
        (i + 1, 10 + i, r) for i, r in enumerate(ROLES)
    ]


def test_400_is_checked_before_touching_the_repo(repo):
    b = body()
    b["name"] = "x" * 21
    with pytest.raises(ApiError) as e:
        FriendlyService(repo).create_friendly(1, b)
    assert (e.value.status_code, e.value.code) == (400, "nameTooLong")
    repo.user_is_playing.assert_not_called()
    repo.create_with_team.assert_not_called()


def test_already_playing(repo):
    repo.user_is_playing.return_value = True
    with pytest.raises(ApiError) as e:
        FriendlyService(repo).create_friendly(1, body())
    assert (e.value.status_code, e.value.code) == (409, "alreadyPlaying")
    repo.create_with_team.assert_not_called()


def test_player_not_owned_or_missing(repo):
    repo.owned_player_ids.side_effect = lambda uid, ids: set(ids) - {3}
    with pytest.raises(ApiError) as e:
        FriendlyService(repo).create_friendly(1, body())
    assert (e.value.status_code, e.value.code) == (409, "playerOrBehaviorNotOwned")
    repo.create_with_team.assert_not_called()


def test_behavior_not_owned_or_missing(repo):
    repo.owned_behavior_ids.side_effect = lambda uid, ids: set(ids) - {12}
    with pytest.raises(ApiError) as e:
        FriendlyService(repo).create_friendly(1, body())
    assert e.value.code == "playerOrBehaviorNotOwned"


def test_already_playing_wins_over_not_owned(repo):
    repo.user_is_playing.return_value = True
    repo.owned_player_ids.side_effect = lambda uid, ids: set()
    with pytest.raises(ApiError) as e:
        FriendlyService(repo).create_friendly(1, body())
    assert e.value.code == "alreadyPlaying"
