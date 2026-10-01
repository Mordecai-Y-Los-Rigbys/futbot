from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.behaviors import MAX_ID, parse_path_id
from app.api.deps import get_behavior_service, get_session_service
from app.errors import ApiError
from app.main import app
from app.repositories.behavior_abstract import BehaviorData
from app.services.behavior_service import BehaviorService
from app.services.session_service import SessionService


def cookies_for(user_id):
    return {"session_id": f"sid-{user_id}"}


def behavior(id=5, user_id=1, name="mi-b", code="print(1)"):
    return BehaviorData(id=id, user_id=user_id, name=name, code=code)


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
    mock.get_owned_behavior.return_value = behavior()
    return mock


@pytest.fixture
def client(session_service, behavior_service):
    app.dependency_overrides[get_session_service] = lambda: session_service
    app.dependency_overrides[get_behavior_service] = lambda: behavior_service
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------- 200 ----------

def test_success_calls_service_with_user_and_id(client, behavior_service):
    behavior_service.get_owned_behavior.return_value = behavior(id=5, user_id=7)

    r = client.get("/behaviors/5", cookies=cookies_for(7))

    assert r.status_code == 200
    assert r.json() == {"id": 5, "name": "mi-b", "code": "print(1)"}  # sin user_id
    behavior_service.get_owned_behavior.assert_called_once_with(7, 5)


# ---------- 401 ----------

def test_no_cookie_returns_401_without_calling_service(client, behavior_service):
    r = client.get("/behaviors/5")

    assert r.status_code == 401
    assert r.json() == {"code": None, "message": "Sin sesión válida."}
    behavior_service.get_owned_behavior.assert_not_called()


def test_unknown_session_returns_401(client, behavior_service):
    r = client.get("/behaviors/5", cookies={"session_id": "no-existe"})

    assert r.status_code == 401
    behavior_service.get_owned_behavior.assert_not_called()


# ---------- 404 ----------

def test_nonexistent_returns_404_with_null_code(client, behavior_service):
    behavior_service.get_owned_behavior.side_effect = ApiError(404, None, "no existe")

    r = client.get("/behaviors/5", cookies=cookies_for(1))

    assert r.status_code == 404
    assert r.json() == {"code": None, "message": "no existe"}


@pytest.mark.parametrize(
    "bad_id", ["abc", "1.5", "0", "-1", "2147483648", "1_0", "+1", "９", "9" * 5000]
)
def test_invalid_id_returns_404_not_400_or_422(client, behavior_service, bad_id):
    r = client.get(f"/behaviors/{bad_id}", cookies=cookies_for(1))

    assert r.status_code == 404
    assert r.json()["code"] is None
    behavior_service.get_owned_behavior.assert_not_called()


def test_empty_id_is_404():
    with pytest.raises(ApiError) as exc:
        parse_path_id("")

    assert exc.value.status_code == 404
    assert exc.value.code is None


# ---------- límites ----------

@pytest.mark.parametrize("valid_id", [1, MAX_ID])
def test_boundary_ids_are_looked_up(client, behavior_service, valid_id):
    behavior_service.get_owned_behavior.return_value = behavior(id=valid_id)

    r = client.get(f"/behaviors/{valid_id}", cookies=cookies_for(1))

    assert r.status_code == 200
    behavior_service.get_owned_behavior.assert_called_once_with(1, valid_id)


def test_above_max_is_404_without_lookup(client, behavior_service):
    r = client.get(f"/behaviors/{MAX_ID + 1}", cookies=cookies_for(1))

    assert r.status_code == 404
    behavior_service.get_owned_behavior.assert_not_called()


# ---------- 403 ----------

def test_other_users_behavior_returns_403_without_leaking(client, behavior_service):
    behavior_service.get_owned_behavior.side_effect = ApiError(403, None, "no es tuyo")

    r = client.get("/behaviors/5", cookies=cookies_for(1))

    assert r.status_code == 403
    assert r.json() == {"code": None, "message": "no es tuyo"}


# ---------- precedencia 401 > 404 > 403 ----------

def test_invalid_id_without_session_is_401(client, behavior_service):
    r = client.get("/behaviors/abc")

    assert r.status_code == 401
    behavior_service.get_owned_behavior.assert_not_called()


def test_invalid_id_with_session_is_404(client):
    assert client.get("/behaviors/abc", cookies=cookies_for(1)).status_code == 404


def test_me_is_not_shadowed_by_id_route(client, behavior_service):
    behavior_service.list_behaviors.return_value = ([], 0)

    r = client.get("/behaviors/me", cookies=cookies_for(1))

    assert r.status_code == 200
    behavior_service.get_owned_behavior.assert_not_called()