import re
from datetime import datetime, timedelta, timezone

import pytest

from app.api.ws_deps import get_friendly_expiry
from app.main import app
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository
from app.schemas.errors import Error, ListPageBadRequest
from app.schemas.friendly import MatchPage

pytestmark = pytest.mark.integration

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
ITEM_FIELDS = {
    "id",
    "leagueId",
    "name",
    "status",
    "club1",
    "club2",
    "scheduledAt",
    "createdAt",
    "result",
}
ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC")


@pytest.fixture()
def rival(create_user):
    return create_user("rival")


@pytest.fixture()
def api(login_as, create_user):
    """Cliente logueado como un usuario espectador."""
    return login_as(create_user("viewer"))


@pytest.fixture()
def make_friendly(db_session):
    def _make(user, name="Amistoso", **fields) -> Match:
        match = Match(user_1_id=user.id, name=name, **fields)
        db_session.add(match)
        db_session.commit()
        return match

    return _make


@pytest.fixture()
def make_friendlies_bulk(db_session):
    def _make(user, names: list[str]) -> list[int]:
        matches = [Match(user_1_id=user.id, name=n) for n in names]
        db_session.add_all(matches)
        db_session.flush()
        ids = [m.id for m in matches]
        db_session.commit()
        return ids

    return _make


class FakeExpiry:
    def __init__(self):
        self.calls = []

    def schedule(self, match_id, created_at=None):
        self.calls.append((match_id, created_at))


@pytest.fixture()
def expiry():
    fake = FakeExpiry()
    app.dependency_overrides[get_friendly_expiry] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_friendly_expiry, None)


def ids(resp):
    return [i["id"] for i in resp.json()["items"]]


def names(resp):
    return {i["name"] for i in resp.json()["items"]}


# --- contrato -----------------------------------------------------------------


def test_contract_with_a_friendly(api, creator, make_friendly):
    make_friendly(creator, "Partido amistoso 1")
    resp = api.get("/friendlies")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    page = MatchPage.model_validate(resp.json())
    assert page.total == 1


def test_empty_database(api):
    resp = api.get("/friendlies")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "page": 1, "pageSize": 50, "total": 0}


def test_item_fields_and_nulls(api, creator, make_friendly):
    match = make_friendly(creator, "Partido amistoso 1")
    item = api.get("/friendlies").json()["items"][0]
    assert set(item) == ITEM_FIELDS
    assert item["id"] == match.id
    assert item["name"] == "Partido amistoso 1"
    assert item["status"] == "scheduled"
    assert item["leagueId"] is None
    assert item["club2"] is None
    assert item["scheduledAt"] is None
    assert item["result"] is None
    assert ISO_UTC.match(item["createdAt"])


def test_club1_uses_username_and_club_name(api, create_user, make_friendly):
    boss = create_user("mgonzalez", "Boca Juniors FC")
    make_friendly(boss)
    club1 = api.get("/friendlies").json()["items"][0]["club1"]
    assert club1 == {"id": boss.id, "username": "mgonzalez", "name": "Boca Juniors FC"}


def test_unknown_params_are_ignored(api, creator, make_friendly):
    make_friendly(creator)
    body = api.get("/friendlies?pageSize=10&foo=bar").json()
    assert body["pageSize"] == 50
    assert len(body["items"]) == 1


# --- qué se lista y qué no ----------------------------------------------------


def test_own_friendlies_are_not_listed(login_as, creator, make_friendly):
    make_friendly(creator, "Mio")
    body = login_as(creator).get("/friendlies").json()
    assert body["items"] == [] and body["total"] == 0


def test_friendly_is_listed_for_other_users_and_not_for_its_creator(
    login_as, create_user, creator, make_friendly
):
    match = make_friendly(creator)
    assert ids(login_as(create_user("otro")).get("/friendlies")) == [match.id]
    assert ids(login_as(creator).get("/friendlies")) == []


def test_friendly_with_rival_is_not_listed_even_if_scheduled(api, creator, rival, make_friendly):
    make_friendly(creator, "Con rival", user_2_id=rival.id)
    body = api.get("/friendlies").json()
    assert body["items"] == [] and body["total"] == 0


def test_started_match_is_not_listed(api, creator, rival, make_friendly):
    make_friendly(creator, user_2_id=rival.id, status=MatchStatus.started)
    assert api.get("/friendlies").json()["items"] == []


def test_finished_match_is_not_listed(api, creator, rival, make_friendly):
    make_friendly(creator, user_2_id=rival.id, status=MatchStatus.finished, score_1=2, score_2=1)
    assert api.get("/friendlies").json()["items"] == []


def test_cancelled_match_is_not_listed(api, creator, make_friendly):
    make_friendly(creator, status=MatchStatus.cancelled)
    assert api.get("/friendlies").json()["items"] == []


def test_league_matches_are_not_listed(api, creator, rival, make_league, make_friendly):
    league = make_league(creator, "Liga")
    make_friendly(
        creator,
        None,
        league_id=league.id,
        user_2_id=rival.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    body = api.get("/friendlies").json()
    assert body["items"] == [] and body["total"] == 0


def test_only_the_waiting_friendly_survives_among_all_kinds(
    api, creator, rival, make_league, make_friendly
):
    waiting = make_friendly(creator, "Esperando")
    make_friendly(creator, "Con rival", user_2_id=rival.id)
    make_friendly(creator, "Empezado", user_2_id=rival.id, status=MatchStatus.started)
    make_friendly(creator, "Cancelado", status=MatchStatus.cancelled)
    league = make_league(creator, "Liga")
    make_friendly(
        creator,
        None,
        league_id=league.id,
        user_2_id=rival.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    resp = api.get("/friendlies")
    assert ids(resp) == [waiting.id]
    assert resp.json()["total"] == 1


def test_friendly_disappears_when_a_rival_joins(api, db_session, creator, rival, make_friendly):
    match = make_friendly(creator)
    assert ids(api.get("/friendlies")) == [match.id]
    match.user_2_id = rival.id
    db_session.commit()
    body = api.get("/friendlies").json()
    assert body["items"] == [] and body["total"] == 0


def test_friendly_disappears_when_cancelled_by_expiry(api, db_session, creator, make_friendly):
    match = make_friendly(creator)
    assert ids(api.get("/friendlies")) == [match.id]
    assert SqlAlchemyMatchExpiryRepository(db_session).cancel_if_waiting_friendly(match.id)
    body = api.get("/friendlies").json()
    assert body["items"] == [] and body["total"] == 0


# --- ciclo completo con POST /friendlies --------------------------------------


def test_friendly_created_with_post_is_listed_for_others_only(
    login_as, create_user, make_behaviors, db_session, expiry
):
    creator = create_user("poster")
    viewer = create_user("watcher")
    players = [
        Player(
            user_id=creator.id,
            name=f"J{i}",
            power=60,
            agility=60,
            control=60,
            strength=60,
            speed=60,
        )
        for i in range(6)
    ]
    db_session.add_all(players)
    db_session.commit()
    behaviors = make_behaviors(creator.id, [f"b{i}" for i in range(6)])
    payload = {
        "name": "Recien creado",
        "members": [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ],
    }

    created = login_as(creator).post("/friendlies", json=payload)
    assert created.status_code == 201, created.text
    match_id = created.json()["id"]

    viewer_api = login_as(viewer)
    assert ids(viewer_api.get("/friendlies")) == [match_id]
    assert ids(login_as(creator).get("/friendlies")) == []

    assert SqlAlchemyMatchExpiryRepository(db_session).cancel_if_waiting_friendly(match_id)
    assert viewer_api.get("/friendlies").json()["items"] == []


# --- orden y paginación -------------------------------------------------------


def test_items_are_ordered_by_id_ascending(api, creator, make_friendlies_bulk):
    created = make_friendlies_bulk(creator, [f"Amistoso {i}" for i in range(10)])
    assert ids(api.get("/friendlies")) == sorted(created)


def test_51_matches_split_into_50_and_1(api, creator, make_friendlies_bulk):
    created = make_friendlies_bulk(creator, [f"Amistoso {i}" for i in range(51)])
    p1, p2 = api.get("/friendlies?page=1"), api.get("/friendlies?page=2")
    assert len(p1.json()["items"]) == 50 and len(p2.json()["items"]) == 1
    assert p1.json()["total"] == 51 and p2.json()["total"] == 51
    assert ids(p1) + ids(p2) == sorted(created)
    assert p1.json()["pageSize"] == 50 and p2.json()["page"] == 2


def test_exactly_50_matches(api, creator, make_friendlies_bulk):
    make_friendlies_bulk(creator, [f"Amistoso {i}" for i in range(50)])
    assert len(api.get("/friendlies?page=1").json()["items"]) == 50
    assert api.get("/friendlies?page=2").json()["items"] == []


def test_page_beyond_last_is_empty_with_real_total(api, creator, make_friendlies_bulk):
    make_friendlies_bulk(creator, [f"Amistoso {i}" for i in range(51)])
    resp = api.get("/friendlies?page=3")
    assert resp.status_code == 200
    assert resp.json()["items"] == [] and resp.json()["total"] == 51


def test_page_upper_limit_is_valid_and_empty(api, creator, make_friendly):
    make_friendly(creator)
    resp = api.get("/friendlies?page=2147483647")
    assert resp.status_code == 200
    assert resp.json()["items"] == [] and resp.json()["total"] == 1


# --- total --------------------------------------------------------------------


def names_of(body):
    return {i["name"] for i in body["items"]}


def test_total_excludes_own_matches(login_as, create_user, creator, make_friendly):
    viewer = create_user("viewer2")
    make_friendly(creator, "Ajeno 1")
    make_friendly(creator, "Ajeno 2")
    make_friendly(viewer, "Propio")
    body = login_as(viewer).get("/friendlies").json()
    assert body["total"] == 2 and names_of(body) == {"Ajeno 1", "Ajeno 2"}


def test_total_respects_name_filter_and_excludes_own(login_as, create_user, creator, make_friendly):
    viewer = create_user("viewer3")
    for n in ("Alfa 1", "Alfa 2", "Beta"):
        make_friendly(creator, n)
    make_friendly(viewer, "Alfa propio")
    api = login_as(viewer)
    assert api.get("/friendlies?name=alfa").json()["total"] == 2
    assert api.get("/friendlies").json()["total"] == 3


# --- filtro por nombre --------------------------------------------------------


@pytest.fixture()
def named(creator, make_friendly):
    for n in ("Liga Argentina", "Liga Boca", "Copa Mundial"):
        make_friendly(creator, n)


def test_filter_returns_only_matches_and_filtered_total(api, named):
    resp = api.get("/friendlies?name=liga")
    assert names(resp) == {"Liga Argentina", "Liga Boca"}
    assert resp.json()["total"] == 2
    assert api.get("/friendlies").json()["total"] == 3


@pytest.mark.parametrize("term", ["BOCA", "boca", "bOcA"])
def test_filter_is_case_insensitive(api, named, term):
    assert names(api.get("/friendlies", params={"name": term})) == {"Liga Boca"}


def test_filter_matches_in_the_middle(api, named):
    assert names(api.get("/friendlies?name=gen")) == {"Liga Argentina"}


def test_filter_without_matches(api, named):
    body = api.get("/friendlies?name=zzz").json()
    assert body["items"] == [] and body["total"] == 0


def test_empty_name_equals_no_filter(api, named):
    assert api.get("/friendlies?name=").json() == api.get("/friendlies").json()


@pytest.fixture()
def special(creator, make_friendly):
    for n in ("100% Liga", "Liga_1", "Liga 1", "Liga\\Uno"):
        make_friendly(creator, n)


@pytest.mark.parametrize(
    "term, expected",
    [
        ("%", {"100% Liga"}),
        ("_", {"Liga_1"}),
        ("\\", {"Liga\\Uno"}),
    ],
)
def test_special_characters_are_literal(api, special, term, expected):
    resp = api.get("/friendlies", params={"name": term})
    assert names(resp) == expected
    assert resp.json()["total"] == len(expected)


def test_filter_combined_with_pagination(api, creator, make_friendlies_bulk):
    make_friendlies_bulk(creator, [f"Alpha {i}" for i in range(75)])
    make_friendlies_bulk(creator, [f"Beta {i}" for i in range(10)])
    body = api.get("/friendlies?name=alpha&page=2").json()
    assert len(body["items"]) == 25
    assert body["total"] == 75


def test_matches_without_name_are_not_matched_by_a_filter(api, creator, make_friendly):
    make_friendly(creator, None)
    assert api.get("/friendlies?name=a").json()["items"] == []
    assert api.get("/friendlies").json()["items"][0]["name"] is None


# --- autenticación (sesiones reales) ------------------------------------------


def test_no_cookie_returns_401(client):
    resp = client.get("/friendlies")
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    Error.model_validate(resp.json())


def test_nonexistent_session_returns_401(client):
    client.cookies.set("session_id", "no-existe")
    assert client.get("/friendlies").status_code == 401


def test_expired_session_returns_401(login_as, create_user):
    expired = login_as(create_user("u"), expires_in=timedelta(days=-1))
    assert expired.get("/friendlies").status_code == 401


def test_deleted_session_returns_401(login_as, create_user, session_repo):
    api = login_as(create_user("u"))
    assert api.get("/friendlies").status_code == 200
    session_repo.delete(api.cookies.get("session_id"))
    assert api.get("/friendlies").status_code == 401


@pytest.mark.parametrize("query", ["page=abc", "page=0", "page=2147483648"])
def test_401_has_priority_over_400(client, query):
    resp = client.get(f"/friendlies?{query}")
    assert resp.status_code == 401 and resp.json()["code"] is None


# --- validación de page -------------------------------------------------------


@pytest.mark.parametrize(
    "query, code",
    [
        ("page=abc", "pageNotAnInteger"),
        ("page=1.5", "pageNotAnInteger"),
        ("page=", "pageNotAnInteger"),
        ("page=0", "pageBelowMinimum"),
        ("page=-1", "pageBelowMinimum"),
        ("page=2147483648", "pageTooLarge"),
    ],
)
def test_invalid_page_returns_400_never_422(api, query, code):
    resp = api.get(f"/friendlies?{query}")
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    assert resp.json()["message"]
    ListPageBadRequest.model_validate(resp.json())


# --- solo lectura y sin N+1 ---------------------------------------------------


def test_endpoint_is_read_only(api, creator, make_friendly, db_session):
    make_friendly(creator, "Amistoso")
    before = db_session.query(Match).count()
    for _ in range(3):
        api.get("/friendlies")
        api.get("/friendlies?name=ami&page=2")
    assert db_session.query(Match).count() == before


@pytest.mark.slow
def test_query_count_does_not_grow_with_friendlies(
    login_as, create_user, make_friendly, db_session, count_queries
):
    api = login_as(create_user("viewer_nplus1"))

    def measure() -> int:
        db_session.expunge_all()
        with count_queries() as statements:
            assert api.get("/friendlies").status_code == 200
        return len(statements)

    make_friendly(create_user("c0"), "A0")
    one = measure()

    for i in range(1, 30):
        make_friendly(create_user(f"c{i}"), f"A{i}")
    many = measure()

    assert one == many
    assert many <= 4
