import random
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, create_autospec

import pytest

from app.api.deps import get_league_service
from app.api.ws_deps import get_league_match_start
from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.main import app
from app.repositories.league_abstract import AbstractLeagueRepository, LeagueStartState
from app.schemas.errors import Error, StartLeagueConflict
from app.services import league_service
from app.services.league_fixture import build_fixture, match_slot
from app.services.league_service import LeagueService
from app.tests.unit.repo_fakes import FakeBehaviors, FakePlayers

NOW = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)
CREATOR = 7  # la valid-session del conftest
URL = "/leagues/5/start"


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def participants_changed(self, league_id):
        self.calls.append(league_id)


def state(**fields):
    base = dict(
        creator_id=CREATOR,
        status=LeagueStatus.preparation,
        min_participants=3,
        participants_count=3,
        match_duration=5,
        allow_draws=True,
    )
    return LeagueStartState(**{**base, **fields})


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(league_service, "_utcnow", lambda: NOW)


@pytest.fixture()
def repo():
    r = create_autospec(AbstractLeagueRepository, instance=True)
    r.get_start_state.return_value = state()
    r.start.return_value = None
    return r


@pytest.fixture()
def notifier():
    return FakeNotifier()


@pytest.fixture()
def match_start():
    fake = AsyncMock()
    app.dependency_overrides[get_league_match_start] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_league_match_start, None)


@pytest.fixture()
def league_api(api, repo, notifier, match_start):
    app.dependency_overrides[get_league_service] = lambda: make_service(repo, notifier)
    return api


def make_service(repo, notifier=None, seed=1):
    return LeagueService(
        repo, FakePlayers(), FakeBehaviors(), notifier=notifier, rng=random.Random(seed)
    )


def error_of(repo, user_id=CREATOR, notifier=None):
    with pytest.raises(ApiError) as exc:
        make_service(repo, notifier).start_league(5, user_id)
    return exc.value


def plan_of(repo):
    league_id, plan = repo.start.call_args.args
    assert league_id == 5
    return plan


def test_success_starts_the_league_and_notifies(repo, notifier):
    make_service(repo, notifier).start_league(5, CREATOR)
    repo.get_start_state.assert_called_once_with(5)
    repo.start.assert_called_once()
    assert notifier.calls == [5]


def test_the_plan_is_the_fixture_of_the_ids_it_receives(repo):
    make_service(repo, seed=3).start_league(5, CREATOR)
    expected = build_fixture([1, 2, 3, 4], NOW, match_slot(5, True), random.Random(3))
    assert plan_of(repo)([1, 2, 3, 4]) == expected


def test_the_plan_uses_the_league_duration_and_mode(repo):
    repo.get_start_state.return_value = state(match_duration=2, allow_draws=False)
    make_service(repo).start_league(5, CREATOR)
    first, second = plan_of(repo)([1, 2, 3])[:2]
    assert first.scheduled_at == NOW + timedelta(minutes=1)
    assert second.scheduled_at - first.scheduled_at == match_slot(2, allow_draws=False)


def test_nonexistent_league_is_404(repo, notifier):
    repo.get_start_state.return_value = None
    err = error_of(repo, notifier=notifier)
    assert (err.status_code, err.code) == (404, None)
    repo.start.assert_not_called()
    assert notifier.calls == []


def test_only_the_creator_can_start_it(repo, notifier):
    err = error_of(repo, user_id=8, notifier=notifier)
    assert (err.status_code, err.code) == (403, None)
    repo.start.assert_not_called()
    assert notifier.calls == []


@pytest.mark.parametrize(
    "status", [LeagueStatus.started, LeagueStatus.cancelled, LeagueStatus.finished]
)
def test_league_not_in_preparation(repo, status):
    repo.get_start_state.return_value = state(status=status)
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "notInPreparation")
    repo.start.assert_not_called()


def test_not_enough_participants(repo):
    repo.get_start_state.return_value = state(participants_count=2, min_participants=3)
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "notEnoughParticipants")
    repo.start.assert_not_called()


@pytest.mark.parametrize("conflict", ["notInPreparation", "notEnoughParticipants"])
def test_losing_the_race_in_the_database_is_reported(repo, notifier, conflict):
    repo.start.return_value = conflict
    err = error_of(repo, notifier=notifier)
    assert (err.status_code, err.code) == (409, conflict)
    assert notifier.calls == []


def test_403_beats_409(repo):
    repo.get_start_state.return_value = state(status=LeagueStatus.started, participants_count=1)
    assert error_of(repo, user_id=8).status_code == 403


def test_not_in_preparation_beats_not_enough_participants(repo):
    repo.get_start_state.return_value = state(status=LeagueStatus.started, participants_count=1)
    assert error_of(repo).code == "notInPreparation"


@pytest.fixture()
def league_api(api, repo, notifier):
    app.dependency_overrides[get_league_service] = lambda: make_service(repo, notifier)
    return api


@pytest.fixture()
def auth_league_api(league_api):
    league_api.cookies.set("session_id", "valid-session")
    return league_api


def test_endpoint_success_is_204_without_body(auth_league_api, repo, match_start):
    resp = auth_league_api.post(URL)
    assert resp.status_code == 204, resp.text
    assert resp.content == b""
    repo.get_start_state.assert_called_once_with(5)
    match_start.schedule_league.assert_awaited_once_with(5)


def test_endpoint_error_schedules_nothing(auth_league_api, repo, match_start):
    repo.get_start_state.return_value = state(creator_id=8)
    assert auth_league_api.post(URL).status_code == 403
    match_start.schedule_league.assert_not_awaited()


@pytest.mark.parametrize("path", [URL, "/leagues/abc/start", "leagues/0/start"])
def test_no_cookie_is_401_even_with_a_bad_id(league_api, repo, path):
    resp = league_api.post(path)
    assert resp.status_code == 401 and resp.json()["code"] is None
    repo.get_start_state.assert_not_called()


@pytest.mark.parametrize("raw_id", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404_without_touching_the_repo(auth_league_api, repo, raw_id):
    resp = auth_league_api.post(f"/leagues/{raw_id}/start")
    assert resp.status_code == 404 and resp.json()["code"] is None
    repo.get_start_state.assert_not_called()
