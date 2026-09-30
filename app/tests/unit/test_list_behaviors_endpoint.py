import pytest

URL = "/behaviors/me"


def names(r):
    return [i["name"] for i in r.json()["items"]]


# ---------- autenticación ----------

def test_no_cookie_returns_401(client):
    r = client.get(URL)
    assert r.status_code == 401
    assert r.json() == {"code": None, "message": "Sin sesión válida."}


def test_invalid_cookie_returns_401(client):
    r = client.get(URL, cookies={"session_id": "no-existe"})
    assert r.status_code == 401
    assert r.json()["code"] is None


@pytest.mark.parametrize("page", ["0", "-1", "abc", "2147483648"])
def test_no_cookie_with_invalid_page_returns_401(client, page):
    r = client.get(URL, params={"page": page})
    assert r.status_code == 401


# ---------- listado y filtro ----------

def test_list_without_filters(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["a", "b", "c"])
    r = client.get(URL, cookies=auth_cookies(1))
    assert r.status_code == 200
    assert names(r) == ["a", "b", "c"]
    assert r.json()["page"] == 1
    assert r.json()["pageSize"] == 50
    assert r.json()["total"] == 3


def test_items_only_have_id_and_name(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["a"])
    r = client.get(URL, cookies=auth_cookies(1))
    assert set(r.json()["items"][0].keys()) == {"id", "name"}


def test_filter_by_name_case_insensitive(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["Patrol Zone", "attack", "PATROL-2"])
    r = client.get(URL, params={"name": "patrol"}, cookies=auth_cookies(1))
    assert names(r) == ["Patrol Zone", "PATROL-2"]
    assert r.json()["total"] == 2


def test_empty_name_equals_no_filter(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["a", "b"])
    r = client.get(URL, params={"name": ""}, cookies=auth_cookies(1))
    assert names(r) == ["a", "b"]
    assert r.json()["total"] == 2


def test_filter_without_matches(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["a", "b"])
    r = client.get(URL, params={"name": "zzz"}, cookies=auth_cookies(1))
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_wildcards_are_literal(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["100%", "abc", "a_c"])
    cookies = auth_cookies(1)
    assert names(client.get(URL, params={"name": "%"}, cookies=cookies)) == ["100%"]
    assert names(client.get(URL, params={"name": "a_c"}, cookies=cookies)) == ["a_c"]


def test_user_isolation(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["shared", "only-1"])
    make_behaviors(2, ["shared", "only-2"])
    cookies = auth_cookies(1)

    r = client.get(URL, cookies=cookies)
    assert names(r) == ["shared", "only-1"]
    assert r.json()["total"] == 2

    r = client.get(URL, params={"name": "only-2"}, cookies=cookies)
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


# ---------- paginación ----------

def test_page_out_of_range_returns_empty_items(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["a", "b"])
    r = client.get(URL, params={"page": 5}, cookies=auth_cookies(1))
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 2  # distinto de "filtro sin coincidencias"
    assert r.json()["page"] == 5


def test_max_page_is_valid(client, auth_cookies, make_behaviors):
    make_behaviors(1, ["a"])
    r = client.get(URL, params={"page": 2147483647}, cookies=auth_cookies(1))
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.parametrize("size_param", ["pageSize", "size", "limit", "page_size"])
def test_size_param_has_no_effect(client, auth_cookies, make_behaviors, size_param):
    make_behaviors(1, [f"b{i:02d}" for i in range(60)])
    r = client.get(URL, params={size_param: 10}, cookies=auth_cookies(1))
    assert r.status_code == 200
    assert len(r.json()["items"]) == 50
    assert r.json()["pageSize"] == 50


def test_pagination_60_items_id_order(client, auth_cookies, make_behaviors):
    rows = make_behaviors(1, [f"b{i:02d}" for i in range(60)])
    ids = sorted(r.id for r in rows)
    cookies = auth_cookies(1)

    p1 = client.get(URL, params={"page": 1}, cookies=cookies).json()
    p2 = client.get(URL, params={"page": 2}, cookies=cookies).json()

    assert [i["id"] for i in p1["items"]] == ids[:50]
    assert [i["id"] for i in p2["items"]] == ids[50:]
    assert p1["total"] == p2["total"] == 60


# ---------- validación de page (400) ----------

@pytest.mark.parametrize("page", ["abc", "1.5", "", " ", "1e3", "+2", "١٢"])
def test_page_not_an_integer(client, auth_cookies, page):
    r = client.get(URL, params={"page": page}, cookies=auth_cookies(1))
    assert r.status_code == 400
    assert r.json()["code"] == "pageNotAnInteger"
    assert set(r.json().keys()) == {"code", "message"}


@pytest.mark.parametrize("page", ["0", "-1", "-999"])
def test_page_below_minimum(client, auth_cookies, page):
    r = client.get(URL, params={"page": page}, cookies=auth_cookies(1))
    assert r.status_code == 400
    assert r.json()["code"] == "pageBelowMinimum"


@pytest.mark.parametrize("page", ["2147483648", "9" * 30, "9" * 5000])
def test_page_too_large(client, auth_cookies, page):
    r = client.get(URL, params={"page": page}, cookies=auth_cookies(1))
    assert r.status_code == 400
    assert r.json()["code"] == "pageTooLarge"