import re
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.schemas.errors import Error, ListPageBadRequest
from app.schemas.league import LeaguePage

pytestmark = pytest.mark.integration

STATUSES = ["preparation", "started", "cancelled", "finished"]
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
ITEM_FIELDS = {
    "id",
    "name",
    "creator",
    "status",
    "participantsCount",
    "maxParticipants",
    "private",
    "createdAt",
}


@pytest.fixture()
def owner(create_user):
    return create_user("owner", "Owner FC")


@pytest.fixture()
def api(login_as, create_user):
    """Cliente logueado como un usuario espectador."""
    return login_as(create_user("viewer"))


def ids(resp):
    return [i["id"] for i in resp.json()["items"]]


# --- contrato -----------------------------------------------------------------


def test_contract_with_leagues(api, owner, make_league):
    make_league(owner, "Liga Argentina")
    resp = api.get("/leagues")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    page = LeaguePage.model_validate(resp.json())
    assert page.total == 1


def test_empty_database(api):
    resp = api.get("/leagues")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "page": 1, "pageSize": 50, "total": 0}


def test_item_fields_and_types(api, owner, make_league):
    make_league(owner, "Liga", status="cancelled", private=True, max_participants=10)
    item = api.get("/leagues").json()["items"][0]
    assert set(item) == ITEM_FIELDS
    assert isinstance(item["id"], int)
    assert isinstance(item["private"], bool) and item["private"] is True
    assert item["status"] in STATUSES
    assert item["maxParticipants"] == 10
    assert ISO_UTC.match(item["createdAt"])


def test_unknown_params_are_ignored(api, owner, make_league):
    make_league(owner)
    body = api.get("/leagues?pageSize=10&foo=bar").json()
    assert body["pageSize"] == 50
    assert len(body["items"]) == 1


def test_endpoint_is_read_only(api, owner, make_league, db_session):
    make_league(owner, "Liga")

    def snapshot():
        return (
            db_session.scalar(select(func.count()).select_from(League)),
            db_session.scalar(select(func.count()).select_from(LeagueParticipant)),
        )

    before = snapshot()
    for _ in range(3):
        api.get("/leagues")
        api.get("/leagues?name=lig&page=2")
    assert snapshot() == before


# --- autenticación (sesiones reales) ------------------------------------------


def test_no_cookie_returns_401(client):
    resp = client.get("/leagues")
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    Error.model_validate(resp.json())


def test_nonexistent_session_returns_401(client):
    client.cookies.set("session_id", "no-existe")
    assert client.get("/leagues").status_code == 401


def test_expired_session_returns_401(login_as, create_user):
    expired = login_as(create_user("u"), expires_in=timedelta(days=-1))
    assert expired.get("/leagues").status_code == 401


def test_deleted_session_returns_401(login_as, create_user, session_repo):
    api = login_as(create_user("u"))
    assert api.get("/leagues").status_code == 200
    session_repo.delete(api.cookies.get("session_id"))  # equivale a un logout
    assert api.get("/leagues").status_code == 401


def test_401_has_priority_over_400(client):
    assert client.get("/leagues?page=abc").status_code == 401


def test_two_users_get_the_same_listing(login_as, create_user, owner, make_league):
    make_league(owner, "Uno")
    make_league(owner, "Dos")
    a = login_as(create_user("a")).get("/leagues").json()
    b = login_as(create_user("b")).get("/leagues").json()
    assert a == b


# --- validación de page (vía HTTP) --------------------------------------------


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
    resp = api.get(f"/leagues?{query}")
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    assert resp.json()["message"]
    ListPageBadRequest.model_validate(resp.json())


def test_page_upper_limit_is_valid_and_empty(api):
    resp = api.get("/leagues?page=2147483647")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_page_lower_limit_is_valid(api, owner, make_league):
    make_league(owner)
    assert api.get("/leagues?page=1").status_code == 200


# --- paginación sobre datos reales --------------------------------------------


def test_three_pages_of_120_leagues(api, owner, make_leagues_bulk):
    created = make_leagues_bulk(owner, [f"Liga {i}" for i in range(120)])
    pages = [api.get(f"/leagues?page={p}") for p in (1, 2, 3)]
    assert [len(p.json()["items"]) for p in pages] == [50, 50, 20]
    assert all(p.json()["total"] == 120 for p in pages)
    assert [i for p in pages for i in ids(p)] == sorted(created)  # sin repetidos ni saltos


def test_page_beyond_last_is_empty_with_total(api, owner, make_leagues_bulk):
    make_leagues_bulk(owner, [f"Liga {i}" for i in range(120)])
    body = api.get("/leagues?page=4").json()
    assert body["items"] == []
    assert body["total"] == 120


def test_exactly_50_leagues(api, owner, make_leagues_bulk):
    make_leagues_bulk(owner, [f"Liga {i}" for i in range(50)])
    assert len(api.get("/leagues?page=1").json()["items"]) == 50
    assert api.get("/leagues?page=2").json()["items"] == []


def test_pagination_is_stable_when_a_league_is_inserted(api, owner, make_leagues_bulk, make_league):
    make_leagues_bulk(owner, [f"Liga {i}" for i in range(60)])
    first = set(ids(api.get("/leagues?page=1")))
    make_league(owner, "Nueva")
    second = set(ids(api.get("/leagues?page=2")))
    assert first.isdisjoint(second)


# --- filtro por nombre contra la DB real --------------------------------------


@pytest.fixture()
def named(owner, make_league):
    for n in ("Liga Argentina", "Liga Boca", "Copa Mundial"):
        make_league(owner, n)


def names(resp):
    return {i["name"] for i in resp.json()["items"]}


def test_filter_returns_only_matches_and_filtered_total(api, named):
    resp = api.get("/leagues?name=liga")
    assert names(resp) == {"Liga Argentina", "Liga Boca"}
    assert resp.json()["total"] == 2
    assert api.get("/leagues").json()["total"] == 3


@pytest.mark.parametrize("term", ["BOCA", "boca", "bOcA"])
def test_filter_is_case_insensitive(api, named, term):
    assert names(api.get("/leagues", params={"name": term})) == {"Liga Boca"}


def test_filter_matches_in_the_middle(api, named):
    assert names(api.get("/leagues?name=gen")) == {"Liga Argentina"}


def test_filter_without_matches(api, named):
    body = api.get("/leagues?name=zzz").json()
    assert body["items"] == []
    assert body["total"] == 0


def test_empty_name_equals_no_filter(api, named):
    assert api.get("/leagues?name=").json() == api.get("/leagues").json()


@pytest.fixture()
def special(owner, make_league):
    for n in ("100% Liga", "Liga_1", "Liga 1", "Liga\\Uno"):
        make_league(owner, n)


@pytest.mark.parametrize(
    "term, expected",
    [
        ("%", {"100% Liga"}),  # no actúa como comodín
        ("_", {"Liga_1"}),  # no matchea "Liga 1"
        ("\\", {"Liga\\Uno"}),
    ],
)
def test_special_characters_are_literal(api, special, term, expected):
    resp = api.get("/leagues", params={"name": term})  # httpx lo url-encodea
    assert names(resp) == expected
    assert resp.json()["total"] == len(expected)


def test_filter_combined_with_pagination(api, owner, make_leagues_bulk):
    make_leagues_bulk(owner, [f"Alpha {i}" for i in range(75)])
    make_leagues_bulk(owner, [f"Beta {i}" for i in range(10)])
    body = api.get("/leagues?name=alpha&page=2").json()
    assert len(body["items"]) == 25
    assert body["total"] == 75


# --- contenido y relaciones ---------------------------------------------------


def test_creator_uses_username_and_club_name(api, create_user, make_league):
    creator = create_user("mgonzalez", "Boca Juniors FC")
    make_league(creator)
    c = api.get("/leagues").json()["items"][0]["creator"]
    assert c == {"id": creator.id, "username": "mgonzalez", "name": "Boca Juniors FC"}


def test_participants_count_of_new_league_is_1(api, owner, make_league):
    make_league(owner)
    assert api.get("/leagues").json()["items"][0]["participantsCount"] == 1


def test_participants_count_includes_creator_and_each_league_has_its_own(
    api, owner, create_user, make_league, add_participant
):
    a, b, c = (make_league(owner, n) for n in ("A", "B", "C"))
    users = [create_user(f"p{i}") for i in range(3)]
    for u in users:  # A: creador + 3
        add_participant(a, u)
    add_participant(b, users[0])  # B: creador + 1
    counts = {i["name"]: i["participantsCount"] for i in api.get("/leagues").json()["items"]}
    assert counts == {"A": 4, "B": 2, "C": 1}  # sin inflado por joins


def test_all_statuses_are_listed(api, owner, make_league):
    for s in STATUSES:
        make_league(owner, s, status=s)
    assert {i["status"] for i in api.get("/leagues").json()["items"]} == set(STATUSES)


def test_private_league_is_listed(api, owner, make_league):
    make_league(owner, "Privada", private=True)
    item = api.get("/leagues").json()["items"][0]
    assert item["private"] is True


# --- performance: sin N+1 -----------------------------------------------------


@pytest.mark.slow
def test_query_count_does_not_grow_with_leagues(
    login_as, create_user, make_league, add_participant, db_session, count_queries
):
    api = login_as(create_user("viewer"))

    def measure() -> int:
        db_session.expunge_all()  # sin identity map: un lazy load sí emitiría SQL
        with count_queries() as statements:
            assert api.get("/leagues").status_code == 200
        return len(statements)

    first = make_league(create_user("c0"), "L0")
    one = measure()

    for i in range(1, 50):
        creator = create_user(f"c{i}")
        league = make_league(creator, f"L{i}")
        add_participant(league, create_user(f"p{i}"))
    fifty = measure()

    assert one == fifty
    assert fifty <= 4  # auth + count + listado
