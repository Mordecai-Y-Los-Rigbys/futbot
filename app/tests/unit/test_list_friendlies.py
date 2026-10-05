from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_friendly_service
from app.main import app
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    FriendlyClubData,
    FriendlyMatchData,
    FriendlyPageData,
)
from app.schemas.errors import Error, ListPageBadRequest
from app.schemas.friendly import MatchPage
from app.services.friendly_service import PAGE_SIZE, FriendlyService

NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)
USER_ID = 7  # el usuario de la sesión "valid-session" del conftest


def match_data(id=100, name="Partido amistoso 1", username="usuario1", club="Club Atletico"):
    return FriendlyMatchData(
        id=id,
        name=name,
        status="scheduled",
        club1=FriendlyClubData(id=1, username=username, club_name=club),
        created_at=NOW,
    )


@pytest.fixture()
def repo():
    r = MagicMock(spec=AbstractFriendlyRepository)
    r.list_waiting_page.return_value = FriendlyPageData(items=[], total=0)
    return r


@pytest.fixture()
def friendlies_api(api, repo):
    """Cliente sin sesión. `api` limpia los overrides al terminar."""
    app.dependency_overrides[get_friendly_service] = lambda: FriendlyService(repo)
    return api


@pytest.fixture()
def auth_friendlies_api(friendlies_api):
    friendlies_api.cookies.set("session_id", "valid-session")
    return friendlies_api


# --- servicio -------------------------------------------------------------------------

def test_service_builds_the_match_page(repo):
    repo.list_waiting_page.return_value = FriendlyPageData(
        items=[match_data(id=100), match_data(id=101)], total=2
    )
    out = FriendlyService(repo).list_waiting_friendlies(USER_ID, None, 1)
    assert isinstance(out, MatchPage)
    assert (out.page, out.page_size, out.total) == (1, 50, 2)
    assert [i.id for i in out.items] == [100, 101]


def test_service_items_follow_the_match_schema(repo):
    repo.list_waiting_page.return_value = FriendlyPageData(items=[match_data()], total=1)
    out = FriendlyService(repo).list_waiting_friendlies(USER_ID, None, 1)
    dumped = out.model_dump(by_alias=True)["items"][0]
    assert dumped["club1"] == {"id": 1, "username": "usuario1", "name": "Club Atletico"}
    for k in ("leagueId", "club2", "scheduledAt", "result"):
        assert dumped[k] is None
    assert "2026-10-03T18:00:00Z" in out.model_dump_json(by_alias=True)


def test_service_accepts_a_match_without_name(repo):
    repo.list_waiting_page.return_value = FriendlyPageData(
        items=[match_data(name=None)], total=1
    )
    out = FriendlyService(repo).list_waiting_friendlies(USER_ID, None, 1)
    assert out.items[0].name is None


@pytest.mark.parametrize("page, offset", [(1, 0), (2, 50), (3, 100), (10, 450)])
def test_service_offset_is_page_minus_one_times_page_size(repo, page, offset):
    out = FriendlyService(repo).list_waiting_friendlies(USER_ID, None, page)
    repo.list_waiting_page.assert_called_once_with(
        exclude_user_id=USER_ID, name=None, offset=offset, limit=PAGE_SIZE
    )
    assert out.page == page


def test_service_empty_name_is_treated_as_absent(repo):
    FriendlyService(repo).list_waiting_friendlies(USER_ID, "", 1)
    assert repo.list_waiting_page.call_args.kwargs["name"] is None


def test_service_passes_name_to_the_repository(repo):
    FriendlyService(repo).list_waiting_friendlies(USER_ID, "boca", 1)
    assert repo.list_waiting_page.call_args.kwargs["name"] == "boca"


def test_service_page_beyond_last_keeps_the_real_total(repo):
    repo.list_waiting_page.return_value = FriendlyPageData(items=[], total=120)
    out = FriendlyService(repo).list_waiting_friendlies(USER_ID, None, 4)
    assert out.items == [] and out.total == 120 and out.page == 4


# --- endpoint: éxito --------------------------------------------------------------------

def test_endpoint_success_full_structure(auth_friendlies_api, repo):
    repo.list_waiting_page.return_value = FriendlyPageData(items=[match_data()], total=1)
    resp = auth_friendlies_api.get("/friendlies")
    assert resp.status_code == 200
    assert resp.json() == {
        "items": [
            {
                "id": 100,
                "leagueId": None,
                "name": "Partido amistoso 1",
                "status": "scheduled",
                "club1": {"id": 1, "username": "usuario1", "name": "Club Atletico"},
                "club2": None,
                "scheduledAt": None,
                "createdAt": "2026-10-03T18:00:00Z",
                "result": None,
            }
        ],
        "page": 1,
        "pageSize": 50,
        "total": 1,
    }
    MatchPage.model_validate(resp.json())


def test_endpoint_empty_list(auth_friendlies_api):
    resp = auth_friendlies_api.get("/friendlies")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "page": 1, "pageSize": 50, "total": 0}


def test_endpoint_excludes_the_logged_user_in_the_query(auth_friendlies_api, repo):
    auth_friendlies_api.get("/friendlies")
    assert repo.list_waiting_page.call_args.kwargs["exclude_user_id"] == USER_ID


def test_endpoint_ignores_page_size_param(auth_friendlies_api, repo):
    body = auth_friendlies_api.get("/friendlies?pageSize=10").json()
    assert body["pageSize"] == 50
    assert repo.list_waiting_page.call_args.kwargs["limit"] == 50


# --- endpoint: paginación -----------------------------------------------------------------

@pytest.mark.parametrize("page, offset", [(1, 0), (2, 50), (3, 100)])
def test_endpoint_pagination_offset_and_page(auth_friendlies_api, repo, page, offset):
    body = auth_friendlies_api.get(f"/friendlies?page={page}").json()
    assert body["page"] == page
    assert repo.list_waiting_page.call_args.kwargs["offset"] == offset
    assert repo.list_waiting_page.call_args.kwargs["limit"] == 50


def test_endpoint_page_without_param_defaults_to_1(auth_friendlies_api, repo):
    assert auth_friendlies_api.get("/friendlies").json()["page"] == 1
    assert repo.list_waiting_page.call_args.kwargs["offset"] == 0


def test_endpoint_page_beyond_last_is_200_with_empty_items(auth_friendlies_api, repo):
    repo.list_waiting_page.return_value = FriendlyPageData(items=[], total=120)
    resp = auth_friendlies_api.get("/friendlies?page=4")
    assert resp.status_code == 200
    assert resp.json()["items"] == [] and resp.json()["total"] == 120


def test_endpoint_upper_limit_page_is_valid(auth_friendlies_api):
    resp = auth_friendlies_api.get("/friendlies?page=2147483647")
    assert resp.status_code == 200 and resp.json()["items"] == []


# --- endpoint: filtro por nombre ---------------------------------------------------------------

def test_endpoint_passes_name_to_the_repository(auth_friendlies_api, repo):
    auth_friendlies_api.get("/friendlies?name=boca")
    assert repo.list_waiting_page.call_args.kwargs["name"] == "boca"


def test_endpoint_empty_name_is_treated_as_absent(auth_friendlies_api, repo):
    auth_friendlies_api.get("/friendlies?name=")
    assert repo.list_waiting_page.call_args.kwargs["name"] is None


def test_endpoint_without_name_is_treated_as_absent(auth_friendlies_api, repo):
    auth_friendlies_api.get("/friendlies")
    assert repo.list_waiting_page.call_args.kwargs["name"] is None


def test_endpoint_name_is_never_validated(auth_friendlies_api, repo):
    resp = auth_friendlies_api.get("/friendlies", params={"name": "x" * 500 + "%_\\"})
    assert resp.status_code == 200


# --- endpoint: autenticación ---------------------------------------------------------------------

def test_no_cookie_returns_401_with_null_code(friendlies_api, repo):
    resp = friendlies_api.get("/friendlies")
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    Error.model_validate(resp.json())
    repo.list_waiting_page.assert_not_called()


@pytest.mark.parametrize("cookie", ["no-existe", "vencida"])
def test_invalid_or_expired_cookie_returns_401(friendlies_api, repo, cookie):
    friendlies_api.cookies.set("session_id", cookie)
    resp = friendlies_api.get("/friendlies")
    assert resp.status_code == 401 and resp.json()["code"] is None
    repo.list_waiting_page.assert_not_called()


@pytest.mark.parametrize("query", ["page=abc", "page=0", "page=2147483648", "page="])
def test_401_has_priority_over_invalid_page(friendlies_api, repo, query):
    resp = friendlies_api.get(f"/friendlies?{query}")
    assert resp.status_code == 401 and resp.json()["code"] is None
    repo.list_waiting_page.assert_not_called()


# --- endpoint: page inválida ------------------------------------------------------------------------

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
def test_invalid_page_returns_400_never_422(auth_friendlies_api, repo, query, code):
    resp = auth_friendlies_api.get(f"/friendlies?{query}")
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    assert resp.json()["message"]
    ListPageBadRequest.model_validate(resp.json())
    repo.list_waiting_page.assert_not_called()