from unittest.mock import MagicMock

import pytest

from app.api.deps import get_match_connection_service
from app.main import app
from app.repositories.match_connection_abstract import (
    AbstractMatchConnectionRepository,
    MatchAccessData,
)
from app.services.match_connection_service import MatchConnectionService


@pytest.fixture()
def repo():
    r = MagicMock(spec=AbstractMatchConnectionRepository)
    r.get_access.return_value = MatchAccessData(id=5, status="scheduled")
    return r


@pytest.fixture()
def conn_api(api, repo):
    app.dependency_overrides[get_match_connection_service] = lambda: MatchConnectionService(repo)
    return api


@pytest.fixture()
def auth_conn_api(conn_api):
    conn_api.cookies.set("session_id", "valid-session")
    return conn_api


def test_success_returns_201_with_token(auth_conn_api, repo):
    r = auth_conn_api.post("/matches/5/connections")
    assert r.status_code == 201
    assert set(r.json()) == {"tokenWs"}
    assert repo.create_token.call_args.args[0].user_id == 7


@pytest.mark.parametrize("kwargs", [
    {}, {"json": {}}, {"json": {"password": 123}},
    {"content": "{", "headers": {"Content-Type": "application/json"}},
])
def test_friendly_accepts_any_body(auth_conn_api, kwargs):
    assert auth_conn_api.post("/matches/5/connections", **kwargs).status_code == 201


def test_no_session_is_401_before_everything(conn_api, repo):
    r = conn_api.post("/matches/abc/connections", json={"password": 1})
    assert r.status_code == 401 and r.json()["code"] is None
    repo.get_access.assert_not_called()


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648", "9" * 5000])
def test_invalid_id_is_404_not_400_or_422(auth_conn_api, repo, bad):
    r = auth_conn_api.post(f"/matches/{bad}/connections", json={"password": 5})
    assert r.status_code == 404 and r.json()["code"] is None
    repo.get_access.assert_not_called()


def test_nonexistent_is_404(auth_conn_api, repo):
    repo.get_access.return_value = None
    assert auth_conn_api.post("/matches/5/connections").status_code == 404


@pytest.mark.parametrize("status, code", [("finished", "matchFinished"), ("cancelled", "matchCancelled")])
def test_409_codes(auth_conn_api, repo, status, code):
    repo.get_access.return_value = MatchAccessData(id=5, status=status)
    r = auth_conn_api.post("/matches/5/connections")
    assert r.status_code == 409 and r.json()["code"] == code