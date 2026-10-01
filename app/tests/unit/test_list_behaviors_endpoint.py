from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_behavior_service, get_session_service
from app.main import app  # ajustá al módulo donde creás la app
from app.repositories.behavior_abstract import BehaviorData
from app.services.behavior_service import PAGE_SIZE, BehaviorService
from app.services.session_service import SessionService

URL = "/behaviors/me"


def cookies_for(user_id):
    return {"session_id": f"sid-{user_id}"}


def behavior(id, name, user_id=1, code="def behave(): pass"):
    return BehaviorData(id=id, user_id=user_id, name=name, code=code)

def names(r):
    return [i["name"] for i in r.json()["items"]]


@pytest.fixture
def session_service():
    mock = create_autospec(SessionService, instance=True)
    # "sid-N" -> user N; anything else -> no valid session
    mock.get_user_id.side_effect = (
        lambda sid: int(sid.removeprefix("sid-")) if sid.startswith("sid-") else None
    )
    return mock


@pytest.fixture
def behavior_service():
    mock = create_autospec(BehaviorService, instance=True)
    mock.list_behaviors.return_value = ([], 0)
    return mock


@pytest.fixture
def client(session_service, behavior_service):
    app.dependency_overrides[get_session_service] = lambda: session_service
    app.dependency_overrides[get_behavior_service] = lambda: behavior_service
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------- autenticación ----------

def test_no_cookie_returns_401(client, behavior_service):
    r = client.get(URL)

    assert r.status_code == 401
    assert r.json() == {"code": None, "message": "Sin sesión válida."}
    behavior_service.list_behaviors.assert_not_called()


def test_invalid_cookie_returns_401(client, behavior_service):
    r = client.get(URL, cookies={"session_id": "no-existe"})

    assert r.status_code == 401
    assert r.json()["code"] is None
    behavior_service.list_behaviors.assert_not_called()


@pytest.mark.parametrize("page", ["0", "-1", "abc", "2147483648"])
def test_no_cookie_with_invalid_page_returns_401(client, page):
    r = client.get(URL, params={"page": page})

    assert r.status_code == 401


# ---------- respuesta ----------

def test_response_body_uses_service_result(client, behavior_service):
    behavior_service.list_behaviors.return_value = (
        [behavior(1, "a"), behavior(2, "b"), behavior(3, "c")],
        3,
    )

    r = client.get(URL, cookies=cookies_for(1))

    assert r.status_code == 200
    assert names(r) == ["a", "b", "c"]
    assert r.json()["page"] == 1
    assert r.json()["pageSize"] == PAGE_SIZE
    assert r.json()["total"] == 3


def test_items_only_have_id_and_name(client, behavior_service):
    # BehaviorData also carries user_id; the endpoint must not expose it
    behavior_service.list_behaviors.return_value = ([behavior(1, "a")], 1)

    r = client.get(URL, cookies=cookies_for(1))

    assert set(r.json()["items"][0].keys()) == {"id", "name"}


def test_empty_result(client):
    r = client.get(URL, cookies=cookies_for(1))

    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_total_is_independent_of_items_returned(client, behavior_service):
    # e.g. a page out of range: no items, but the total is preserved
    behavior_service.list_behaviors.return_value = ([], 2)

    r = client.get(URL, params={"page": 5}, cookies=cookies_for(1))

    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 2
    assert r.json()["page"] == 5


# ---------- qué le pasa el endpoint al servicio ----------

def test_service_receives_user_from_session(client, behavior_service):
    client.get(URL, cookies=cookies_for(7))

    behavior_service.list_behaviors.assert_called_once_with(
        user_id=7, name=None, page=1
    )


def test_service_receives_name_and_page(client, behavior_service):
    client.get(URL, params={"name": "patrol", "page": 3}, cookies=cookies_for(1))

    behavior_service.list_behaviors.assert_called_once_with(
        user_id=1, name="patrol", page=3
    )


def test_max_page_is_valid(client, behavior_service):
    r = client.get(URL, params={"page": 2147483647}, cookies=cookies_for(1))

    assert r.status_code == 200
    behavior_service.list_behaviors.assert_called_once_with(
        user_id=1, name=None, page=2147483647
    )


@pytest.mark.parametrize("size_param", ["pageSize", "size", "limit", "page_size"])
def test_size_param_has_no_effect(client, behavior_service, size_param):
    r = client.get(URL, params={size_param: 10}, cookies=cookies_for(1))

    assert r.status_code == 200
    assert r.json()["pageSize"] == PAGE_SIZE
    behavior_service.list_behaviors.assert_called_once_with(
        user_id=1, name=None, page=1
    )


# ---------- validación de page (400) ----------

@pytest.mark.parametrize("page", ["abc", "1.5", "", " ", "1e3", "+2", "١٢"])
def test_page_not_an_integer(client, behavior_service, page):
    r = client.get(URL, params={"page": page}, cookies=cookies_for(1))

    assert r.status_code == 400
    assert r.json()["code"] == "pageNotAnInteger"
    assert set(r.json().keys()) == {"code", "message"}
    behavior_service.list_behaviors.assert_not_called()


@pytest.mark.parametrize("page", ["0", "-1", "-999"])
def test_page_below_minimum(client, behavior_service, page):
    r = client.get(URL, params={"page": page}, cookies=cookies_for(1))

    assert r.status_code == 400
    assert r.json()["code"] == "pageBelowMinimum"
    behavior_service.list_behaviors.assert_not_called()


@pytest.mark.parametrize("page", ["2147483648", "9" * 30, "9" * 5000])
def test_page_too_large(client, behavior_service, page):
    r = client.get(URL, params={"page": page}, cookies=cookies_for(1))

    assert r.status_code == 400
    assert r.json()["code"] == "pageTooLarge"
    behavior_service.list_behaviors.assert_not_called()