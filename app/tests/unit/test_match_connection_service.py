from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.errors import ApiError
from app.repositories.match_connection_abstract import (
    AbstractMatchConnectionRepository,
    MatchAccessData,
)
from app.services import match_connection_service
from app.services.match_connection_service import MatchConnectionService
from app.services.match_timing import WS_TOKEN_TTL

NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(match_connection_service, "_utcnow", lambda: NOW)


@pytest.fixture()
def repo():
    r = MagicMock(spec=AbstractMatchConnectionRepository)
    r.get_access.return_value = MatchAccessData(id=5, status="scheduled")
    r.is_league_participant.return_value = False
    return r


def private_league(status="started", creator=1):
    return MatchAccessData(
        id=5, status=status, league_id=9, league_creator_id=creator,
        league_private=True, league_password="secret",
    )


def error_of(service, user_id=7, match_id=5, body=None):
    with pytest.raises(ApiError) as e:
        service.connect(user_id, match_id, body)
    return e.value.status_code, e.value.code


# --- éxito / amistoso ---

@pytest.mark.parametrize("body", [None, {}, {"password": 123}, {"password": "x"}, [1], "x"])
def test_friendly_ignores_body_entirely(repo, body):
    token = MatchConnectionService(repo).connect(7, 5, body)
    assert token
    repo.is_league_participant.assert_not_called()


def test_token_is_bound_to_user_and_match_with_ttl(repo):
    token = MatchConnectionService(repo).connect(7, 5, None)
    data = repo.create_token.call_args.args[0]
    assert (data.token, data.user_id, data.match_id) == (token, 7, 5)
    assert data.created_at == NOW and data.expires_at - data.created_at == WS_TOKEN_TTL
    assert len(token) <= 64


def test_each_call_creates_a_different_token(repo):
    s = MatchConnectionService(repo)
    assert s.connect(7, 5, None) != s.connect(7, 5, None)


def test_waiting_friendly_does_not_change_the_match(repo):
    MatchConnectionService(repo).connect(7, 5, None)
    assert [c[0] for c in repo.method_calls] == ["get_access", "create_token"]


# --- 404 / 409 ---

def test_nonexistent_match_is_404(repo):
    repo.get_access.return_value = None
    assert error_of(MatchConnectionService(repo)) == (404, None)
    repo.create_token.assert_not_called()


@pytest.mark.parametrize(
    "status, code", [("finished", "matchFinished"), ("cancelled", "matchCancelled")]
)
def test_finished_or_cancelled_is_409_without_token(repo, status, code):
    repo.get_access.return_value = MatchAccessData(id=5, status=status)
    assert error_of(MatchConnectionService(repo)) == (409, code)
    repo.create_token.assert_not_called()


# --- liga privada ---

def test_outsider_with_non_string_password_is_400(repo):
    repo.get_access.return_value = private_league()
    assert error_of(MatchConnectionService(repo), body={"password": 5}) == (400, "invalidFieldType")


@pytest.mark.parametrize("body", [{"password": "mala"}, {}, None, {"password": None}])
def test_outsider_with_wrong_or_missing_password_is_403(repo, body):
    repo.get_access.return_value = private_league()
    assert error_of(MatchConnectionService(repo), body=body) == (403, "invalidLeaguePassword")
    repo.create_token.assert_not_called()


def test_outsider_with_correct_password_gets_token(repo):
    repo.get_access.return_value = private_league()
    assert MatchConnectionService(repo).connect(7, 5, {"password": "secret"})


def test_participant_and_creator_need_no_password(repo):
    repo.get_access.return_value = private_league()
    repo.is_league_participant.return_value = True
    assert MatchConnectionService(repo).connect(7, 5, None)
    repo.is_league_participant.return_value = False
    assert MatchConnectionService(repo).connect(1, 5, None)  # creador


def test_public_league_ignores_password(repo):
    repo.get_access.return_value = MatchAccessData(
        id=5, status="started", league_id=9, league_creator_id=1, league_private=False
    )
    assert MatchConnectionService(repo).connect(7, 5, {"password": 123})


def test_precedence_400_403_409(repo):
    s = MatchConnectionService(repo)
    repo.get_access.return_value = private_league(status="finished")
    assert error_of(s, body={"password": 5})[0] == 400      # 400 > 409
    assert error_of(s, body={"password": "mala"})[0] == 403  # 403 > 409
    assert error_of(s, body={"password": "secret"})[0] == 409