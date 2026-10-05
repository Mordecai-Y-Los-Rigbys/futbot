from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_behavior_service, get_session_service
from app.main import app  # ajustá al módulo donde creás la app
from app.repositories.behavior_abstract import BehaviorData
from app.services.behavior_service import PAGE_SIZE, BehaviorService
from app.services.session_service import SessionService

URL = "/behaviors/me"


def behavior(id, name, user_id=1, code="def behave(): pass"):
    return BehaviorData(id=id, user_id=user_id, name=name, code=code)


def names(r):
    return [i["name"] for i in r.json()["items"]]


@pytest.fixture
def session_service():
    mock = create_autospec(SessionService, instance=True)
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


@pytest.fixture
def as_user(client):
    """as_user(7) -> el mismo cliente con la cookie de la sesión del usuario 7."""

    def _as(user_id):
        client.cookies.clear()
        client.cookies.set("session_id", f"sid-{user_id}")
        return client

    return _as


# ---------- autenticación ----------

def test_no_cookie_returns_401(client, behavior_service):
    r = client.get(URL)

    assert r.status_code == 401
    assert r.json() == {"code": None, "message": "Sin sesión válida."}
    behavior_service.list_behaviors.assert_not_called()


def test_invalid_cookie_returns_401(client, behavior_service):
    client.cookies.set("session_id", "no-existe")

    r = client.get(URL)

    assert r.status_code == 401
    assert r.json()["code"] is None
    behavior_service.list_behaviors.assert_not_called()


@pytest.mark.parametrize("page", ["0", "-1", "abc", "2147483648"])
def test_no_cookie_with_invalid_page_returns_401(client, page):
    r = client.get(URL, params={"page": page})

    assert r.status_code == 401


# ---------- respuesta ----------

def test_response_body_uses_service_result(as_user, behavior_service):
    behavior_service.list_behaviors.return_value = (
        [behavior(1, "a"), behavior(2, "b"), behavior(3, "c")],
        3,
    )

    r = as_user(1).get(URL)

    assert r.status_code == 200
    assert names(r) == ["a", "b", "c"]
    assert r.json()["page"] == 1
    assert r.json()["pageSize"] == PAGE_SIZE
    assert r.json()["total"] == 3


def test_items_only_have_id_and_name(as_user, behavior_service):
    behavior_service.list_behaviors.return_value = ([behavior(1, "a")], 1)

    r = as_user(1).get(URL)

    assert set(r.json()["items"][0].keys()) == {"id", "name"}


def test_empty_result(as_user):
    r = as_user(1).get(URL)

    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_total_is_independent_of_items_returned(as_user, behavior_service):
    behavior_service.list_behaviors.return_value = ([], 2)

    r = as_user(1).get(URL, params={"page": 5})

    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 2
    assert r.json()["page"] == 5


# ---------- qué le pasa el endpoint al servicio ----------

def test_service_receives_user_from_session(as_user, behavior_service):
    as_user(7).get(URL)

    behavior_service.list_behaviors.assert_called_once_with(
        user_id=7, name=None, page=1
    )


def test_service_receives_name_and_page(as_user, behavior_service):
    as_user(1).get(URL, params={"name": "patrol", "page": 3})

    behavior_service.list_behaviors.assert_called_once_with(
        user_id=1, name="patrol", page=3
    )


def test_max_page_is_valid(as_user, behavior_service):
    r = as_user(1).get(URL, params={"page": 2147483647})

    assert r.status_code == 200
    behavior_service.list_behaviors.assert_called_once_with(
        user_id=1, name=None, page=2147483647
    )


@pytest.mark.parametrize("size_param", ["pageSize", "size", "limit", "page_size"])
def test_size_param_has_no_effect(as_user, behavior_service, size_param):
    r = as_user(1).get(URL, params={size_param: 10})

    assert r.status_code == 200
    assert r.json()["pageSize"] == PAGE_SIZE
    behavior_service.list_behaviors.assert_called_once_with(
        user_id=1, name=None, page=1
    )


# ---------- validación de page (400) ----------

@pytest.mark.parametrize("page", ["abc", "1.5", "", " ", "1e3", "+2", "١٢"])
def test_page_not_an_integer(as_user, behavior_service, page):
    r = as_user(1).get(URL, params={"page": page})

    assert r.status_code == 400
    assert r.json()["code"] == "pageNotAnInteger"
    assert set(r.json().keys()) == {"code", "message"}
    behavior_service.list_behaviors.assert_not_called()


@pytest.mark.parametrize("page", ["0", "-1", "-999"])
def test_page_below_minimum(as_user, behavior_service, page):
    r = as_user(1).get(URL, params={"page": page})

    assert r.status_code == 400
    assert r.json()["code"] == "pageBelowMinimum"
    behavior_service.list_behaviors.assert_not_called()


@pytest.mark.parametrize("page", ["2147483648", "9" * 30, "9" * 5000])
def test_page_too_large(as_user, behavior_service, page):
    r = as_user(1).get(URL, params={"page": page})

    assert r.status_code == 400
    assert r.json()["code"] == "pageTooLarge"
    behavior_service.list_behaviors.assert_not_called()