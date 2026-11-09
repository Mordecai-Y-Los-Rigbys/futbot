from datetime import datetime, timezone

import pytest

from app.domain.match import MatchStatus
from app.models.match import Match

pytestmark = pytest.mark.integration

F = MatchStatus.finished
DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def creator(create_user):
    return create_user("creator")


@pytest.fixture()
def public_league(creator, make_league):
    return make_league(creator, "Publica", status="started")


@pytest.fixture()
def add_match(db_session):
    def _add(league, u1, u2, s1=0, s2=0, penalty_winner=None, status=F):
        finished = status == F
        match = Match(
            league_id=league.id if league else None,
            user_1_id=u1.id,
            user_2_id=u2.id,
            status=status,
            scheduled_at=DATE if league else None,
            score_1=s1 if finished else None,
            score_2=s2 if finished else None,
            penalty_score_1=(4 if penalty_winner == 1 else 3) if penalty_winner else None,
            penalty_score_2=(3 if penalty_winner == 1 else 4) if penalty_winner else None,
            penalty_winner=penalty_winner,
            penalty_kicks=[] if penalty_winner else None,
        )
        db_session.add(match)
        db_session.commit()
        return match

    return _add


@pytest.fixture()
def users(create_user):
    return [create_user(n, club_name=f"Club {n}") for n in ("a", "b", "c", "d")]


def get(api, query=""):
    return api.get(f"/ranking{query}")


def names(resp):
    return [i["name"] for i in resp.json()["items"]]


# --- acceso y validación -------------------------------------------------------


def test_no_cookie_is_401(client):
    r = get(client)
    assert r.status_code == 401 and r.json()["code"] is None


def test_401_beats_invalid_page(client):
    assert get(client, "?page=abc").status_code == 401


@pytest.mark.parametrize(
    "query, reason",
    [
        ("page=abc", "invalidType"),
        ("page=1.5", "invalidType"),
        ("page=", "invalidType"),
        ("page=0", "outOfRange"),
        ("page=2147483648", "outOfRange"),
    ],
)
def test_invalid_page_is_400(login_as, creator, query, reason):
    r = get(login_as(creator), f"?{query}")
    assert r.status_code == 400
    assert r.json()["code"] == "invalidFields"
    assert r.json()["errors"] == [{"field": "page", "reason": reason}]


# --- vacíos --------------------------------------------------------------------


def test_no_finished_matches(login_as, creator):
    r = get(login_as(creator))
    assert r.status_code == 200
    assert r.json() == {"items": [], "page": 1, "pageSize": 50, "total": 0}


def test_page_beyond_last_and_unmatched_name(login_as, creator, public_league, add_match, users):
    add_match(public_league, users[0], users[1], 1, 0)
    api = login_as(creator)
    r = get(api, "?page=2")
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 2
    r = get(api, "?name=zzz")
    assert r.json()["items"] == [] and r.json()["total"] == 0


# --- qué suma y qué no ---------------------------------------------------------


def test_only_finished_public_league_matches_count(
    login_as, creator, public_league, make_league, add_match, users
):
    a, b, c, d = users
    private = make_league(creator, "Privada", status="started", private=True)
    preparing = make_league(creator, "Prep", status="preparation")
    add_match(public_league, a, b, 1, 0)  # el único que suma
    add_match(private, c, d, 5, 0)  # liga privada
    add_match(None, c, d, 5, 0)  # amistoso
    add_match(public_league, c, d, status=MatchStatus.started)  # sin terminar
    add_match(public_league, c, d, status=MatchStatus.scheduled)
    add_match(preparing, c, d, 5, 0)  # liga todavía en preparación
    r = get(login_as(creator))
    assert names(r) == ["Club a", "Club b"]
    assert r.json()["total"] == 2


def test_entry_values_regular_win(login_as, creator, public_league, add_match, users):
    add_match(public_league, users[0], users[1], 3, 1)
    items = get(login_as(creator)).json()["items"]
    assert items[0] == {
        "position": 1,
        "name": "Club a",
        "avatar": 1,
        "score": 3,
        "goalDifference": 2,
        "goals": 3,
        "wonRegular": 1,
        "wonPenalties": 0,
        "lost": 0,
    }
    assert items[1]["score"] == 0 and items[1]["lost"] == 1
    assert items[1]["goalDifference"] == -2 and items[1]["goals"] == 1


@pytest.mark.parametrize("winner", [1, 2])
def test_penalty_win_gives_2_points_and_no_penalty_goals(
    login_as, creator, public_league, add_match, users, winner
):
    add_match(public_league, users[0], users[1], 2, 2, penalty_winner=winner)
    items = {i["name"]: i for i in get(login_as(creator)).json()["items"]}
    won, lost = (
        (items["Club a"], items["Club b"]) if winner == 1 else (items["Club b"], items["Club a"])
    )
    assert (won["score"], won["wonPenalties"], won["wonRegular"]) == (2, 1, 0)
    assert (lost["score"], lost["lost"], lost["wonPenalties"]) == (0, 1, 0)
    assert won["goals"] == lost["goals"] == 2  # los penales no suman goles
    assert won["goalDifference"] == lost["goalDifference"] == 0


def test_draw_gives_1_point(login_as, creator, public_league, add_match, users):
    add_match(public_league, users[0], users[1], 1, 1)
    items = get(login_as(creator)).json()["items"]
    assert [i["score"] for i in items] == [1, 1]
    assert [i["position"] for i in items] == [1, 1]


# --- orden ---------------------------------------------------------------------


def test_orders_by_score_then_goal_difference(login_as, creator, public_league, add_match, users):
    a, b, c, d = users
    add_match(public_league, a, b, 1, 0)  # a: 3 pts, DG +1
    add_match(public_league, c, d, 5, 0)  # c: 3 pts, DG +5
    assert names(get(login_as(creator)))[:2] == ["Club c", "Club a"]


def test_won_penalties_break_ties_after_won_regular(
    login_as, creator, public_league, add_match, users
):
    a, b, c, d = users
    # a: gana por penales (2) + empata (1) = 3 pts. c: gana 1-0... se evita: c: 3 empates
    # c y d empatan tres veces entre sí en dos ligas distintas no hace falta: usamos 3 ligas.
    add_match(public_league, a, b, 1, 1, penalty_winner=1)  # a 2 pts
    add_match(public_league, a, c, 1, 1)  # a 3 pts, goles 2, DG 0
    add_match(public_league, c, d, 1, 1)  # c: 2 pts
    add_match(public_league, c, d, 1, 1)
    add_match(public_league, c, d, 1, 1)  # c: 4 pts
    r = get(login_as(creator))
    scores = {i["name"]: i["score"] for i in r.json()["items"]}
    assert scores["Club a"] == 3 and scores["Club c"] == 4
    assert names(r)[0] == "Club c"


def test_tied_clubs_are_ordered_by_id_and_paginate_stably(
    login_as, creator, public_league, add_match, create_user
):
    clubs = [create_user(f"u{i:02d}", club_name=f"Club {i:02d}") for i in range(56)]
    for i in range(0, 56, 2):
        add_match(public_league, clubs[i], clubs[i + 1], 0, 0)  # 56 clubes empatados en todo
    api = login_as(creator)
    p1, p2 = get(api, "?page=1"), get(api, "?page=2")
    assert len(p1.json()["items"]) == 50 and len(p2.json()["items"]) == 6
    assert p1.json()["total"] == p2.json()["total"] == 56
    assert names(p1) + names(p2) == [f"Club {i:02d}" for i in range(56)]
    assert {i["position"] for i in p1.json()["items"] + p2.json()["items"]} == {1}


# --- filtro --------------------------------------------------------------------


def test_name_filter_is_partial_case_insensitive_and_keeps_position(
    login_as, creator, public_league, add_match, users
):
    a, b, c, d = users
    add_match(public_league, a, b, 3, 0)
    add_match(public_league, c, d, 1, 0)
    api = login_as(creator)
    r = get(api, "?name=CLUB D")
    assert names(r) == ["Club d"]
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["position"] == 3  # lo que ocupa en el ranking completo
    assert get(api, "?name=").json()["total"] == 4


def test_endpoint_is_read_only(login_as, creator, public_league, add_match, users, db_session):
    add_match(public_league, users[0], users[1], 1, 0)
    before = db_session.query(Match).count()
    get(login_as(creator))
    assert db_session.query(Match).count() == before
