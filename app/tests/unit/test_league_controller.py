import pytest

from app.repositories.league_abstract import LeaguePageData
from app.schemas.errors import ListPageBadRequest
from app.schemas.league import LeaguePage

ITEM_FIELDS = {
    "id", "name", "creator", "status",
    "participantsCount", "maxParticipants", "private", "createdAt",
}


# --- autenticación ---------------------------------------------------------

def test_no_cookie_returns_401(api, fake_repo):
    resp = api.get("/leagues")
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    assert resp.json()["message"]
    assert fake_repo.calls == []


def test_invalid_cookie_returns_401(api, fake_repo):
    api.cookies.set("session_id", "no-existe")
    resp = api.get("/leagues")
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    assert fake_repo.calls == []


def test_401_has_priority_over_invalid_page(api, fake_repo):
    resp = api.get("/leagues?page=abc")
    assert resp.status_code == 401
    assert fake_repo.calls == []


# --- validación de page -----------------------------------------------------

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
def test_invalid_page_returns_400_never_422(auth_api, fake_repo, query, code):
    resp = auth_api.get(f"/leagues?{query}")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == code
    assert body["message"]
    ListPageBadRequest.model_validate(body)
    assert fake_repo.calls == []


def test_page_upper_limit_is_valid(auth_api, fake_repo):
    resp = auth_api.get("/leagues?page=2147483647")
    assert resp.status_code == 200
    assert fake_repo.calls[0]["offset"] == (2147483647 - 1) * 50


def test_page_defaults_to_1(auth_api, fake_repo):
    resp = auth_api.get("/leagues")
    assert resp.status_code == 200
    assert resp.json()["page"] == 1
    assert fake_repo.calls[0]["offset"] == 0


# --- name -------------------------------------------------------------------

def test_empty_name_is_treated_as_absent(auth_api, fake_repo):
    auth_api.get("/leagues?name=")
    assert fake_repo.calls[0]["name"] is None


def test_name_reaches_the_repository_untouched(auth_api, fake_repo):
    auth_api.get("/leagues", params={"name": "100%_\\"})  # httpx lo url-encodea
    assert fake_repo.calls[0]["name"] == "100%_\\"


# --- respuesta --------------------------------------------------------------

def test_response_shape(auth_api, fake_repo, make_item):
    fake_repo.page = LeaguePageData(
        items=[make_item(id=1), make_item(id=2, status="cancelled")], total=2
    )
    resp = auth_api.get("/leagues")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    LeaguePage.model_validate(body)
    assert set(body) == {"items", "page", "pageSize", "total"}
    assert set(body["items"][0]) == ITEM_FIELDS
    assert body["items"][0]["creator"] == {
        "id": 7, "username": "mgonzalez", "name": "Boca Juniors FC",
    }
    assert body["items"][0]["createdAt"] == "2026-01-01T00:00:00Z"
    assert [i["status"] for i in body["items"]] == ["preparation", "cancelled"]


def test_page_size_param_is_ignored(auth_api, fake_repo):
    resp = auth_api.get("/leagues?pageSize=10&foo=bar")
    assert resp.status_code == 200
    assert resp.json()["pageSize"] == 50
    assert fake_repo.calls[0]["limit"] == 50


def test_no_matches_returns_empty_page(auth_api, fake_repo):
    fake_repo.page = LeaguePageData(items=[], total=0)
    body = auth_api.get("/leagues?name=zzz").json()
    assert body["items"] == []
    assert body["total"] == 0