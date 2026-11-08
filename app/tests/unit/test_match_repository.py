from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.match import Match, MatchStatus
from app.repositories.league_access_abstract import LeagueAccessInfo
from app.repositories.match_abstract import PenaltyShootoutData
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository

CREATED = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def _user(user_id, avatar=1):
    return SimpleNamespace(
        id=user_id,
        username=f"user{user_id}",
        club_name=f"club{user_id}",
        avatar=avatar,
    )


def _match(**fields):
    base = dict(
        id=5,
        league_id=None,
        name="Amistoso",
        status=MatchStatus.scheduled,
        user_1=_user(1),
        user_2=None,
        scheduled_at=None,
        created_at=CREATED,
        score_1=None,
        score_2=None,
        league=None,
        penalty_score_1=None,
        penalty_score_2=None,
        penalty_winner=None,
        penalty_kicks=None,
    )
    return SimpleNamespace(**(base | fields))


@pytest.fixture()
def db():
    return MagicMock(spec=Session)


@pytest.fixture()
def repo(db):
    return SqlAlchemyMatchRepository(db)


def test_returns_none_when_the_match_does_not_exist(repo, db):
    db.get.return_value = None
    assert repo.get_state(99) is None
    db.get.assert_called_once_with(Match, 99)


@pytest.mark.parametrize(
    "status",
    [MatchStatus.scheduled, MatchStatus.started, MatchStatus.finished, MatchStatus.cancelled],
)
def test_state(repo, db, status):
    db.get.return_value = SimpleNamespace(id=5, status=status)
    state = repo.get_state(5)
    assert state.id == 5
    assert state.status == status


def test_is_read_only(repo, db):
    db.get.return_value = SimpleNamespace(id=5, status=MatchStatus.finished)
    repo.get_state(5)
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_detail_is_none_when_the_match_does_not_exist(repo, db):
    db.get.return_value = None
    assert repo.get_detail(99) is None
    db.get.assert_called_once_with(Match, 99, options=ANY)


def test_detail_of_a_waiting_friendly_has_no_rival_and_no_league(repo, db):
    db.get.return_value = _match()
    out = repo.get_detail(5)
    assert out.club2 is None and out.league is None
    assert out.club1.club_name == "club1"


def test_detail_of_a_league_match_maps_both_clubs_and_the_league(repo, db):
    league = SimpleNamespace(id=9, creator_id=1, private=True, password="secret")
    db.get.return_value = _match(
        league_id=9,
        name=None,
        user_1=_user(1, avatar=2),
        user_2=_user(2, avatar=4),
        league=league,
        status=MatchStatus.finished,
        score_1=2,
        score_2=1,
    )
    out = repo.get_detail(5)
    assert (out.club1.avatar, out.club2.avatar) == (2, 4)
    assert out.league == LeagueAccessInfo(9, 1, True, "secret")
    assert (out.score_1, out.score_2) == (2, 1)


def test_detail_of_a_match_with_shootout_has_the_penalties(repo, db):
    kicks = [{"club": "club1", "kickerId": 3, "kickerName": "J3", "round": 1, "scored": True}]
    db.get.return_value = _match(
        status=MatchStatus.finished,
        score_1=1,
        score_2=1,
        penalty_score_1=1,
        penalty_score_2=0,
        penalty_winner=2,
        penalty_kicks=kicks,
    )
    out = repo.get_detail(5)
    assert out.penalties == PenaltyShootoutData(score_1=1, score_2=0, winner=2, kicks=kicks)
