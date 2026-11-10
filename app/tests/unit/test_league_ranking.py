import pytest

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.services.ranking_service import RankingService
from app.tests.unit.repo_fakes import FakeRankingRepo, ranking_club as club


def ranking(clubs, status=LeagueStatus.started):
    return RankingService(FakeRankingRepo(clubs, status)).get_league_ranking(1)


def names(entries):
    return [e.name for e in entries]


# --- estado de la liga ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, code",
    [(LeagueStatus.preparation, "leagueNotStarted"), (LeagueStatus.cancelled, "leagueCancelled")],
)
def test_league_without_ranking_is_409(status, code):
    with pytest.raises(ApiError) as exc:
        ranking([club(1)], status=status)
    assert (exc.value.status_code, exc.value.code) == (409, code)
    assert exc.value.message


@pytest.mark.parametrize("status", [LeagueStatus.started, LeagueStatus.finished])
def test_started_or_finished_league_has_ranking(status):
    assert len(ranking([club(1)], status=status)) == 1


# --- entradas ------------------------------------------------------------------


def test_just_started_everyone_at_zero_and_first():
    r = ranking([club(3), club(1), club(2)])
    assert names(r) == ["Club 1", "Club 2", "Club 3"]
    for e in r:
        assert e.position == 1
        assert (e.played, e.won_regular, e.won_penalties, e.drawn, e.lost) == (0, 0, 0, 0, 0)
        assert (e.goals, e.goal_difference, e.score) == (0, 0, 0)


def test_entry_fields():
    e = ranking([club(1, "A", wr=1, wp=1, d=2, l=3, gf=5, ga=3, avatar=4)])[0]
    assert (e.position, e.name, e.avatar, e.played) == (1, "A", 4, 7)
    assert (e.won_regular, e.won_penalties, e.drawn, e.lost) == (1, 1, 2, 3)
    assert (e.goals, e.goal_difference) == (5, 2)


def test_score_counts_3_2_1_0():
    regular, penalties, draw, loss = ranking([club(1, wr=1), club(2, wp=1), club(3, d=1), club(4, l=1)])
    assert [regular.score, penalties.score, draw.score, loss.score] == [3, 2, 1, 0]


def test_empty_league_ranking():
    assert ranking([]) == []


# --- un test por criterio ------------------------------------------------------


def test_orders_by_score_first():
    assert names(ranking([club(1, "bajo", d=1, gf=50), club(2, "alto", wr=1)])) == ["alto", "bajo"]


def test_goal_difference_breaks_score_ties():
    r = ranking([club(1, "A", d=3, gf=3, ga=3), club(2, "B", wr=1, gf=2, ga=0)])
    assert names(r) == ["B", "A"]


def test_goals_break_goal_difference_ties():
    r = ranking([club(1, "A", wr=1, gf=1, ga=0), club(2, "B", wr=1, gf=4, ga=3)])
    assert names(r) == ["B", "A"]


def test_won_regular_breaks_goals_ties():
    r = ranking([club(1, "B", d=3, gf=3, ga=3), club(2, "A", wr=1, gf=3, ga=3)])
    assert r[0].score == r[1].score == 3
    assert names(r) == ["A", "B"]


def test_won_penalties_break_won_regular_ties():
    r = ranking([club(1, "B", d=3, gf=3, ga=3), club(2, "A", wp=1, d=1, gf=3, ga=3)])
    assert r[0].score == r[1].score == 3
    assert names(r) == ["A", "B"]


def test_lost_is_ascending():
    r = ranking([club(1, "perdio2", d=3, l=2, gf=2, ga=2), club(2, "perdio0", d=3, gf=2, ga=2)])
    assert names(r) == ["perdio0", "perdio2"]


# --- position y desempates -----------------------------------------------------


def test_ties_share_position_and_next_is_skipped():
    r = ranking([club(1, wr=3), club(2, wr=2), club(3, wr=2), club(4, wr=1)])
    assert [e.position for e in r] == [1, 2, 2, 4]


def test_clubs_tied_in_everything_are_ordered_by_club_id():
    r = ranking([club(30, "C", d=1), club(10, "A", d=1), club(20, "B", d=1)])
    assert names(r) == ["A", "B", "C"]
    assert {e.position for e in r} == {1}


def test_one_criterion_different_means_different_position():
    r = ranking([club(1, d=1, l=1), club(2, d=1)])
    assert [e.position for e in r] == [1, 2]
    assert r[0].lost == 0