import pytest

from app.api.deps import get_ranking_service
from app.main import app
from app.services.ranking_service import PAGE_SIZE, RankingService
from app.tests.unit.repo_fakes import FakeRankingRepo, ranking_club as club

def ranking(clubs, page=1, name=None):
    return RankingService(FakeRankingRepo(clubs)).get_global_ranking(page, name)


def ids_by_name(result):
    return [e.name for e in result.items]


# --- puntaje -------------------------------------------------------------------


def test_score_counts_3_2_1_0():
    r = ranking([club(1, wr=2, wp=1, d=1, l=5)])
    assert r.items[0].score == 3 * 2 + 2 * 1 + 1


def test_entry_fields():
    r = ranking([club(1, "A", wr=1, wp=1, d=0, l=2, gf=5, ga=3, avatar=4)])
    e = r.items[0]
    assert (e.position, e.name, e.avatar) == (1, "A", 4)
    assert (e.goal_difference, e.goals, e.won_regular, e.won_penalties, e.lost) == (2, 5, 1, 1, 2)


# --- un test por criterio ------------------------------------------------------


def test_orders_by_score_first():
    r = ranking([club(1, "bajo", d=1, gf=50), club(2, "alto", wr=1)])
    assert ids_by_name(r) == ["alto", "bajo"]


def test_goal_difference_breaks_score_ties():
    r = ranking([club(1, "A", d=3, gf=3, ga=3), club(2, "B", wr=1, d=0, gf=2, ga=0, l=0)])
    # B: 3 pts, DG +2; A: 3 pts, DG 0
    assert ids_by_name(r) == ["B", "A"]


def test_goals_break_goal_difference_ties():
    # Mismo puntaje y DG +1; B convirtió más goles.
    r = ranking([club(1, "A", wr=1, gf=1, ga=0), club(2, "B", wr=1, gf=4, ga=3)])
    assert ids_by_name(r) == ["B", "A"]


def test_won_regular_breaks_goals_ties():
    # A: 3 pts (1 ganado). B: 3 pts (3 empates). Mismo DG (0) y goles (3).
    r = ranking([club(1, "B", d=3, gf=3, ga=3), club(2, "A", wr=1, d=0, gf=3, ga=3)])
    assert r.items[0].score == r.items[1].score == 3
    assert ids_by_name(r) == ["A", "B"]


def test_won_penalties_break_won_regular_ties():
    # A: 1 ganado por penales + 1 empate = 3 pts. B: 3 empates = 3 pts.
    r = ranking([club(1, "B", d=3, gf=3, ga=3), club(2, "A", wp=1, d=1, gf=3, ga=3)])
    assert r.items[0].score == r.items[1].score == 3
    assert ids_by_name(r) == ["A", "B"]


def test_lost_is_ascending():
    r = ranking([club(1, "perdio2", d=3, l=2, gf=2, ga=2), club(2, "perdio0", d=3, l=0, gf=2, ga=2)])
    assert ids_by_name(r) == ["perdio0", "perdio2"]


# --- position y desempates -----------------------------------------------------


def test_ties_share_position_and_next_is_skipped():
    r = ranking([club(1, wr=3), club(2, wr=2), club(3, wr=2), club(4, wr=1)])
    assert [e.position for e in r.items] == [1, 2, 2, 4]


def test_clubs_tied_in_everything_are_ordered_by_club_id():
    r = ranking([club(30, "C", d=1), club(10, "A", d=1), club(20, "B", d=1)])
    assert ids_by_name(r) == ["A", "B", "C"]
    assert {e.position for e in r.items} == {1}


def test_one_criterion_different_means_different_position():
    r = ranking([club(1, d=1, l=1), club(2, d=1, l=0)])
    assert [e.position for e in r.items] == [1, 2]
    assert r.items[0].lost == 0


# --- filtro --------------------------------------------------------------------


def clubs_40():
    return [club(i, f"Club {i:02d}", wr=100 - i) for i in range(1, 41)]


def test_name_filter_is_partial_and_case_insensitive():
    r = ranking([club(1, "Boca Juniors", wr=2), club(2, "River", wr=1)], name="BOCA")
    assert ids_by_name(r) == ["Boca Juniors"]
    assert r.total == 1


def test_empty_name_does_not_filter():
    assert ranking(clubs_40(), name="").total == 40


def test_filter_does_not_change_position():
    r = ranking(clubs_40(), name="Club 40")
    assert r.items[0].position == 40
    assert r.total == 1


def test_name_without_matches():
    r = ranking(clubs_40(), name="zzz")
    assert r.items == [] and r.total == 0


# --- paginación ----------------------------------------------------------------


def test_empty_ranking():
    r = ranking([])
    assert (r.items, r.page, r.page_size, r.total) == ([], 1, PAGE_SIZE, 0)


def test_pages_split_without_repeating_or_skipping():
    clubs = [club(i, d=1) for i in range(1, 56)]  # todos empatados: 55 clubes
    p1, p2 = ranking(clubs, page=1), ranking(clubs, page=2)
    assert len(p1.items) == 50 and len(p2.items) == 5
    assert p1.total == p2.total == 55
    assert ids_by_name(p1) + ids_by_name(p2) == [f"Club {i}" for i in range(1, 56)]
    assert p2.items[0].position == 1  # el empate cruza el corte de página


def test_page_beyond_last_is_empty_with_total():
    r = ranking(clubs_40(), page=2)
    assert r.items == [] and r.total == 40 and r.page == 2


# --- endpoint ------------------------------------------------------------------


@pytest.fixture()
def ranking_api(api):
    repo = FakeRankingRepo([club(1, "A", wr=1, gf=2, ga=1), club(2, "B")])
    app.dependency_overrides[get_ranking_service] = lambda: RankingService(repo)
    return api


@pytest.fixture()
def auth_ranking_api(ranking_api):
    ranking_api.cookies.set("session_id", "valid-session")
    return ranking_api


def test_no_cookie_is_401(ranking_api):
    r = ranking_api.get("/ranking")
    assert r.status_code == 401 and r.json()["code"] is None


@pytest.mark.parametrize("query", ["page=abc", "page=0", "page=2147483648", "page="])
def test_401_beats_400(ranking_api, query):
    assert ranking_api.get(f"/ranking?{query}").status_code == 401


@pytest.mark.parametrize("query", ["page=abc", "page=1.5", "page="])
def test_page_not_an_integer(auth_ranking_api, query):
    r = auth_ranking_api.get(f"/ranking?{query}")
    assert r.status_code == 400
    assert r.json()["code"] == "invalidFields"
    assert r.json()["errors"] == [{"field": "page", "reason": "invalidType"}]


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=2147483648", "page=" + "9" * 5000])
def test_page_out_of_range(auth_ranking_api, query):
    r = auth_ranking_api.get(f"/ranking?{query}")
    assert r.status_code == 400
    assert r.json()["errors"] == [{"field": "page", "reason": "outOfRange"}]


def test_success_shape(auth_ranking_api):
    r = auth_ranking_api.get("/ranking")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "page", "pageSize", "total"}
    assert (body["page"], body["pageSize"], body["total"]) == (1, 50, 2)
    assert set(body["items"][0]) == {
        "position", "name", "avatar", "score", "goalDifference",
        "goals", "wonRegular", "wonPenalties", "lost",
    }


def test_max_page_is_valid_and_empty(auth_ranking_api):
    r = auth_ranking_api.get("/ranking?page=2147483647")
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 2


def test_empty_name_is_ignored(auth_ranking_api):
    assert auth_ranking_api.get("/ranking?name=").json()["total"] == 2