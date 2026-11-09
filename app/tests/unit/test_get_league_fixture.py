from datetime import datetime, timezone

import pytest

from app.api.deps import get_league_access_service
from app.domain.match import MatchStatus
from app.errors import ApiError
from app.main import app
from app.repositories.league_abstract import (
    LeagueFixtureClubData,
    LeagueFixtureData,
    LeagueFixtureMatchData,
)
from app.repositories.league_access_abstract import LeagueAccessInfo
from app.services.league_access_service import LeagueAccessService

USER_ID = 7  # el de "valid-session" en FakeSessionService
CREATOR_ID = 99
URL = "/leagues/1/fixture"


class FakeAccessRepository:
    def __init__(self):
        self.leagues: dict[int, LeagueAccessInfo] = {}
        self.participants: set[tuple[int, int]] = set()
        self.unlocked: set[tuple[str, int]] = set()

    def get_league(self, league_id):
        return self.leagues.get(league_id)

    def is_participant(self, league_id, user_id):
        return (league_id, user_id) in self.participants

    def is_unlocked(self, session_id, league_id):
        return (session_id, league_id) in self.unlocked

    def unlock(self, session_id, league_id):
        self.unlocked.add((session_id, league_id))


def club(id, avatar=1):
    return LeagueFixtureClubData(id=id, username=f"user{id}", club_name=f"club{id}", avatar=avatar)


def match(id, hour=10, status=MatchStatus.scheduled, score=None):
    return LeagueFixtureMatchData(
        id=id,
        status=status,
        club_1=club(USER_ID),
        club_2=club(CREATOR_ID, avatar=3),
        scheduled_at=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        score_1=score[0] if score else None,
        score_2=score[1] if score else None,
    )


def fixture_data(status="started", matches=()):
    return LeagueFixtureData(status=status, matches=list(matches))


@pytest.fixture()
def fake_access():
    return FakeAccessRepository()


@pytest.fixture()
def fixture_api(api, fake_access, fake_repo):
    # `api` limpia los overrides al terminar
    app.dependency_overrides[get_league_access_service] = lambda: LeagueAccessService(fake_access)
    fake_access.leagues[1] = LeagueAccessInfo(1, CREATOR_ID, False, None)
    fake_repo.fixtures[1] = fixture_data(matches=[match(1)])
    return api


@pytest.fixture()
def auth_fixture_api(fixture_api):
    fixture_api.cookies.set("session_id", "valid-session")
    return fixture_api


def make_private(fake_access, creator_id=CREATOR_ID):
    fake_access.leagues[1] = LeagueAccessInfo(1, creator_id, True, "secret")


# ---------- service ----------


def test_service_maps_a_finished_match_to_the_contract(service, fake_repo):
    fake_repo.fixtures[5] = fixture_data(
        "finished", [match(1, status=MatchStatus.finished, score=(2, 1))]
    )

    [result] = service.get_fixture(5)

    assert result.model_dump(by_alias=True, mode="json") == {
        "id": 1,
        "leagueId": 5,
        "name": None,
        "status": "finished",
        "club1": {"id": USER_ID, "username": "user7", "name": "club7", "avatar": 1},
        "club2": {"id": CREATOR_ID, "username": "user99", "name": "club99", "avatar": 3},
        "scheduledAt": "2026-01-01T10:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "result": {"score1": 2, "score2": 1, "penalties": None},
    }
    assert fake_repo.fixture_calls == [5]


@pytest.mark.parametrize("status", [MatchStatus.scheduled, MatchStatus.started])
def test_service_result_is_null_if_the_match_did_not_finish(service, fake_repo, status):
    fake_repo.fixtures[5] = fixture_data(matches=[match(1, status=status)])
    assert service.get_fixture(5)[0].result is None


def test_service_keeps_the_repository_order(service, fake_repo):
    fake_repo.fixtures[5] = fixture_data(matches=[match(3, 9), match(1, 10), match(2, 11)])
    assert [m.id for m in service.get_fixture(5)] == [3, 1, 2]


@pytest.mark.parametrize("status", ["started", "finished"])
def test_service_returns_the_fixture_of_a_started_or_finished_league(service, fake_repo, status):
    fake_repo.fixtures[5] = fixture_data(status, [match(1)])
    assert len(service.get_fixture(5)) == 1


def test_service_missing_league_raises_404(service):
    with pytest.raises(ApiError) as exc:
        service.get_fixture(5)
    assert exc.value.status_code == 404
    assert exc.value.code is None


@pytest.mark.parametrize(
    "status, code", [("preparation", "leagueNotStarted"), ("cancelled", "leagueCancelled")]
)
def test_service_league_without_fixture_raises_409(service, fake_repo, status, code):
    fake_repo.fixtures[5] = fixture_data(status)

    with pytest.raises(ApiError) as exc:
        service.get_fixture(5)

    assert exc.value.status_code == 409
    assert exc.value.code == code


# ---------- endpoint: 401 / 404 ----------


@pytest.mark.parametrize("league_id", ["1", "abc", "0", "99"])
def test_without_session_returns_401_for_any_id(fixture_api, league_id):
    response = fixture_api.get(f"/leagues/{league_id}/fixture")
    assert response.status_code == 401
    assert response.json()["code"] is None


def test_invalid_session_returns_401(fixture_api):
    fixture_api.cookies.set("session_id", "invalid")
    assert fixture_api.get(URL).status_code == 401


@pytest.mark.parametrize("league_id", ["abc", "0", "-1", "2147483648", "1.5", "99"])
def test_invalid_or_missing_id_returns_404(auth_fixture_api, fake_repo, league_id):
    response = auth_fixture_api.get(f"/leagues/{league_id}/fixture")

    assert response.status_code == 404
    assert response.json()["code"] is None
    assert fake_repo.fixture_calls == []


# ---------- endpoint: acceso ----------


def test_public_league_returns_200_to_any_user(auth_fixture_api):
    assert auth_fixture_api.get(URL).status_code == 200


def test_private_league_returns_200_to_the_creator(auth_fixture_api, fake_access):
    make_private(fake_access, creator_id=USER_ID)
    assert auth_fixture_api.get(URL).status_code == 200


def test_private_league_returns_200_to_a_participant(auth_fixture_api, fake_access):
    make_private(fake_access)
    fake_access.participants.add((1, USER_ID))
    assert auth_fixture_api.get(URL).status_code == 200


def test_private_league_returns_200_if_the_session_unlocked_it(auth_fixture_api, fake_access):
    make_private(fake_access)
    fake_access.unlocked.add(("valid-session", 1))
    assert auth_fixture_api.get(URL).status_code == 200


def test_private_league_without_access_returns_403(auth_fixture_api, fake_access, fake_repo):
    make_private(fake_access)

    response = auth_fixture_api.get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"
    assert fake_repo.fixture_calls == []


def test_unlock_of_another_session_does_not_count(auth_fixture_api, fake_access):
    make_private(fake_access)
    fake_access.unlocked.add(("other-session", 1))
    assert auth_fixture_api.get(URL).status_code == 403


# ---------- endpoint: 409 ----------


@pytest.mark.parametrize(
    "status, code", [("preparation", "leagueNotStarted"), ("cancelled", "leagueCancelled")]
)
def test_league_without_fixture_returns_409(auth_fixture_api, fake_repo, status, code):
    fake_repo.fixtures[1] = fixture_data(status)

    response = auth_fixture_api.get(URL)

    assert response.status_code == 409
    assert response.json()["code"] == code


def test_access_does_not_guarantee_200(auth_fixture_api, fake_access, fake_repo):
    make_private(fake_access)
    fake_access.unlocked.add(("valid-session", 1))
    fake_repo.fixtures[1] = fixture_data("preparation")

    response = auth_fixture_api.get(URL)

    assert response.status_code == 409
    assert response.json()["code"] == "leagueNotStarted"


# ---------- endpoint: orden de evaluación ----------


def test_401_goes_before_404(fixture_api):
    assert fixture_api.get("/leagues/abc/fixture").status_code == 401


def test_401_goes_before_403(fixture_api, fake_access):
    make_private(fake_access)
    assert fixture_api.get(URL).status_code == 401


def test_404_goes_before_403(auth_fixture_api, fake_access):
    make_private(fake_access)
    assert auth_fixture_api.get("/leagues/99/fixture").status_code == 404


def test_403_goes_before_409(auth_fixture_api, fake_access, fake_repo):
    make_private(fake_access)
    fake_repo.fixtures[1] = fixture_data("preparation")
    assert auth_fixture_api.get(URL).status_code == 403


# ---------- endpoint: contenido ----------


def test_returns_the_matches_with_camel_case_fields(auth_fixture_api):
    response = auth_fixture_api.get(URL)

    assert response.status_code == 200
    [item] = response.json()
    assert item["leagueId"] == 1
    assert item["scheduledAt"] == "2026-01-01T10:00:00Z"
    assert item["club2"]["avatar"] == 3
    assert item["result"] is None


def test_openapi_operation():
    operation = app.openapi()["paths"]["/leagues/{id}/fixture"]["get"]
    assert operation["operationId"] == "getLeagueFixture"
    assert {"200", "401", "403", "404", "409"} <= operation["responses"].keys()
    assert "requestBody" not in operation
    params = operation.get("parameters", [])
    assert [p["name"] for p in params if p["in"] in ("path", "query", "header")] == ["id"]
