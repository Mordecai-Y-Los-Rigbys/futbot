import pytest

from app.domain.league import LeagueStatus
from app.services.league_ranking_channel import LeagueRankingState, build_ranking_payload
from app.services.ranking_service import RankingService
from app.tests.unit.repo_fakes import FakeRankingRepo, ranking_club as club


def payload(clubs, status=LeagueStatus.started):
    return build_ranking_payload(LeagueRankingState(status=status, clubs=clubs))


def test_payload_matches_the_contract():
    a = club(1, "A", wr=1, wp=1, d=2, l=3, gf=5, ga=3, avatar=4)
    assert payload([a]) == {
        "type": "leagueRanking",
        "leagueStatus": "started",
        "ranking": [
            {
                "position": 1,
                "name": "A",
                "avatar": 4,
                "played": 7,
                "wonRegular": 1,
                "wonPenalties": 1,
                "drawn": 2,
                "lost": 3,
                "goals": 5,
                "goalDifference": 2,
                "score": 7,
            }
        ],
    }


def test_the_ranking_is_the_same_as_get_ranking():
    clubs = [club(4, wr=1), club(1, wr=3), club(3, wr=2, gf=2), club(2, wr=2, gf=2), club(5, l=2)]
    rest = RankingService(FakeRankingRepo(clubs)).get_league_ranking(1)
    assert payload(clubs)["ranking"] == [e.model_dump(mode="json", by_alias=True) for e in rest]


def test_ties_share_position():
    ranking = payload([club(1, wr=3), club(2, wr=2), club(3, wr=2), club(4, wr=1)])["ranking"]
    assert [e["position"] for e in ranking] == [1, 2, 2, 4]


def test_just_started_league_has_everyone_at_zero():
    ranking = payload([club(3), club(1), club(2)])["ranking"]
    assert [e["name"] for e in ranking] == ["Club 1", "Club 2", "Club 3"]
    for e in ranking:
        assert e["position"] == 1
        assert (e["played"], e["score"], e["goals"], e["goalDifference"]) == (0, 0, 0, 0)


def test_cancelled_league_has_an_empty_ranking():
    message = payload([club(1, wr=1)], status=LeagueStatus.cancelled)
    assert (message["leagueStatus"], message["ranking"]) == ("cancelled", [])


@pytest.mark.parametrize("status", [LeagueStatus.started, LeagueStatus.finished])
def test_started_or_finished_league_keeps_its_ranking(status):
    message = payload([club(1, wr=1), club(2, l=1)], status=status)
    assert (message["leagueStatus"], len(message["ranking"])) == (status.value, 2)
