from datetime import timedelta

import pytest

from app.errors import ApiError
from app.services import match_handshake_service
from app.services.match_handshake_service import MatchHandshakeService
from app.tests.unit.match_ws_fakes import NOW, FakeMatchRepo, FakeTokenRepo


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(match_handshake_service, "_utcnow", lambda: NOW)


@pytest.fixture()
def tokens():
    repo = FakeTokenRepo()
    repo.add("tok", user_id=7, match_id=1)
    return repo


@pytest.fixture()
def matches():
    repo = FakeMatchRepo()
    repo.add(1)
    return repo


@pytest.fixture()
def service(tokens, matches):
    return MatchHandshakeService(tokens, matches)


def reject(service, token, match_id="1"):
    with pytest.raises(ApiError) as exc:
        service.authorize(token, match_id)
    return exc.value


# --- éxito -------------------------------------------------------------------

def test_valid_token_returns_user_and_match(service):
    grant = service.authorize("tok", "1")
    assert (grant.user_id, grant.match_id) == (7, 1)


def test_token_can_be_reused(service):
    assert service.authorize("tok", "1") == service.authorize("tok", "1")


# --- 401 ----------------------------------------------------------------------

@pytest.mark.parametrize("token", [None, ""])
def test_missing_token_is_401_without_touching_the_repository(service, tokens, token):
    err = reject(service, token)
    assert (err.status_code, err.code) == (401, None)
    assert tokens.lookups == []


def test_unknown_token_is_401(service):
    err = reject(service, "no-existe")
    assert (err.status_code, err.code) == (401, None)


def test_overlong_token_is_401_without_touching_the_repository(service, tokens):
    assert reject(service, "x" * 65).status_code == 401
    assert tokens.lookups == []


def test_token_expired_one_second_ago_is_401(service, tokens):
    tokens.add("viejo", match_id=1, expires_at=NOW - timedelta(seconds=1))
    assert reject(service, "viejo").status_code == 401


def test_token_expiring_exactly_now_is_401(service, tokens):
    tokens.add("justo", match_id=1, expires_at=NOW)
    assert reject(service, "justo").status_code == 401


def test_token_expiring_in_one_second_is_valid(service, tokens):
    tokens.add("vigente", user_id=9, match_id=1, expires_at=NOW + timedelta(seconds=1))
    assert service.authorize("vigente", "1").user_id == 9


# --- 403 ----------------------------------------------------------------------

def test_token_of_another_match_is_403(service, matches):
    matches.add(2)
    err = reject(service, "tok", match_id="2")
    assert (err.status_code, err.code) == (403, None)


@pytest.mark.parametrize("raw", ["abc", "1.5", "", "01x", "-1", "99999999999999999999", "１"])
def test_non_matching_or_non_numeric_id_is_403(service, raw):
    assert reject(service, "tok", match_id=raw).status_code == 403


def test_token_of_another_match_on_a_nonexistent_match_is_403_not_404(service):
    # El orden es token -> asociación -> existencia: quien no tiene un token
    # de ese partido no se entera de si existe.
    assert reject(service, "tok", match_id="999").status_code == 403


# --- 404 / 409 ------------------------------------------------------------------

def test_nonexistent_match_is_404(service, tokens):
    tokens.add("huerfano", match_id=5)  # token que apunta a un partido que no existe
    err = reject(service, "huerfano", match_id="5")
    assert (err.status_code, err.code) == (404, None)


def test_finished_match_is_409_match_finished(service, matches):
    matches.add(1, finished=True)
    err = reject(service, "tok")
    assert (err.status_code, err.code) == (409, "matchFinished")


# --- orden de validación ------------------------------------------------------------

def test_expired_token_beats_finished_match(service, tokens, matches):
    tokens.add("viejo", match_id=1, expires_at=NOW - timedelta(days=1))
    matches.add(1, finished=True)
    assert reject(service, "viejo").status_code == 401


def test_wrong_match_beats_finished_match(service, matches):
    matches.add(1, finished=True)
    matches.add(2)
    assert reject(service, "tok", match_id="2").status_code == 403


def test_nonexistent_match_beats_finished_check(service, tokens):
    tokens.add("huerfano", match_id=5)
    assert reject(service, "huerfano", match_id="5").status_code == 404