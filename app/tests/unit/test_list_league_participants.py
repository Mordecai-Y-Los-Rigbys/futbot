import pytest

from app.api.deps import get_league_access_service
from app.main import app
from app.repositories.league_abstract import LeagueParticipantData
from app.repositories.league_access_abstract import LeagueAccessInfo
from app.services.league_access_service import LeagueAccessService

USER_ID = 7  # el de "valid-session" en FakeSessionService
CREATOR_ID = 99


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


def participant(id, username=None, club_name=None, avatar=1):
    return LeagueParticipantData(
        id=id,
        username=username or f"user{id}",
        club_name=club_name or f"club{id}",
        avatar=avatar,
    )


@pytest.fixture()
def fake_access():
    return FakeAccessRepository()


@pytest.fixture()
def participants_api(api, fake_access, fake_repo):
    # `api` limpia los overrides al terminar
    app.dependency_overrides[get_league_access_service] = lambda: LeagueAccessService(fake_access)
    fake_access.leagues[1] = LeagueAccessInfo(1, CREATOR_ID, False, None)
    fake_repo.participant_lists[1] = [participant(USER_ID), participant(CREATOR_ID)]
    return api


@pytest.fixture()
def auth_participants_api(participants_api):
    participants_api.cookies.set("session_id", "valid-session")
    return participants_api


def make_private(fake_access, league_id=1, creator_id=CREATOR_ID):
    fake_access.leagues[league_id] = LeagueAccessInfo(league_id, creator_id, True, "secret")


# ---------- service ----------


def test_service_maps_club_name_to_name(service, fake_repo):
    fake_repo.participant_lists[5] = [participant(3, "mgonzalez", "Boca Juniors FC", 4)]

    result = service.list_participants(5)

    assert [p.model_dump() for p in result] == [
        {"id": 3, "username": "mgonzalez", "name": "Boca Juniors FC", "avatar": 4}
    ]
    assert fake_repo.participants_calls == [5]


def test_service_keeps_the_repository_order(service, fake_repo):
    fake_repo.participant_lists[5] = [participant(2), participant(5), participant(9)]
    assert [p.id for p in service.list_participants(5)] == [2, 5, 9]


def test_service_returns_empty_list(service):
    assert service.list_participants(5) == []


# ---------- endpoint: 401 / 404 ----------


@pytest.mark.parametrize("league_id", ["1", "abc", "0", "99"])
def test_without_session_returns_401_for_any_id(participants_api, league_id):
    response = participants_api.get(f"/leagues/{league_id}/participants")
    assert response.status_code == 401
    assert response.json()["code"] is None


def test_invalid_session_returns_401(participants_api):
    participants_api.cookies.set("session_id", "invalid")
    assert participants_api.get("/leagues/1/participants").status_code == 401


@pytest.mark.parametrize("league_id", ["abc", "0", "-1", "2147483648", "1.5", "99"])
def test_invalid_or_missing_id_returns_404(auth_participants_api, fake_repo, league_id):
    response = auth_participants_api.get(f"/leagues/{league_id}/participants")

    assert response.status_code == 404
    assert response.json()["code"] is None
    assert fake_repo.participants_calls == []


# ---------- endpoint: acceso ----------


def test_public_league_returns_200_to_any_user(auth_participants_api):
    assert auth_participants_api.get("/leagues/1/participants").status_code == 200


def test_private_league_returns_200_to_the_creator(auth_participants_api, fake_access):
    make_private(fake_access, creator_id=USER_ID)
    assert auth_participants_api.get("/leagues/1/participants").status_code == 200


def test_private_league_returns_200_to_a_participant(auth_participants_api, fake_access):
    make_private(fake_access)
    fake_access.participants.add((1, USER_ID))
    assert auth_participants_api.get("/leagues/1/participants").status_code == 200


def test_private_league_returns_200_if_the_session_unlocked_it(auth_participants_api, fake_access):
    make_private(fake_access)
    fake_access.unlocked.add(("valid-session", 1))
    assert auth_participants_api.get("/leagues/1/participants").status_code == 200


def test_private_league_without_access_returns_403(auth_participants_api, fake_access, fake_repo):
    make_private(fake_access)

    response = auth_participants_api.get("/leagues/1/participants")

    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"
    assert fake_repo.participants_calls == []


def test_unlock_of_another_session_does_not_count(auth_participants_api, fake_access):
    make_private(fake_access)
    fake_access.unlocked.add(("other-session", 1))
    assert auth_participants_api.get("/leagues/1/participants").status_code == 403


def test_unlock_of_another_league_does_not_count(auth_participants_api, fake_access):
    make_private(fake_access)
    fake_access.unlocked.add(("valid-session", 2))
    assert auth_participants_api.get("/leagues/1/participants").status_code == 403


# ---------- endpoint: orden de evaluación ----------


def test_401_goes_before_404(participants_api):
    assert participants_api.get("/leagues/abc/participants").status_code == 401


def test_401_goes_before_403(participants_api, fake_access):
    make_private(fake_access)
    assert participants_api.get("/leagues/1/participants").status_code == 401


def test_404_goes_before_403(auth_participants_api, fake_access):
    make_private(fake_access)
    assert auth_participants_api.get("/leagues/99/participants").status_code == 404


# ---------- endpoint: contenido ----------


def test_returns_the_list_with_only_user_club_fields(auth_participants_api, fake_repo):
    fake_repo.participant_lists[1] = [
        participant(3, "a", "Club A", 2),
        participant(CREATOR_ID, "mgonzalez", "Boca Juniors FC", 5),
    ]

    response = auth_participants_api.get("/leagues/1/participants")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 3, "username": "a", "name": "Club A", "avatar": 2},
        {"id": CREATOR_ID, "username": "mgonzalez", "name": "Boca Juniors FC", "avatar": 5},
    ]
    assert fake_repo.participants_calls == [1]


def test_empty_list_returns_200(auth_participants_api, fake_repo):
    fake_repo.participant_lists[1] = []

    response = auth_participants_api.get("/leagues/1/participants")

    assert response.status_code == 200
    assert response.json() == []


def test_response_does_not_include_the_password(auth_participants_api, fake_access):
    make_private(fake_access, creator_id=USER_ID)

    response = auth_participants_api.get("/leagues/1/participants")

    assert "secret" not in response.text
    assert all("password" not in p for p in response.json())


def test_openapi_operation():
    operation = app.openapi()["paths"]["/leagues/{id}/participants"]["get"]
    assert operation["operationId"] == "listLeagueParticipants"
    assert {"200", "401", "403", "404"} <= operation["responses"].keys()
    assert "requestBody" not in operation
    params = operation.get("parameters", [])
    assert [p["name"] for p in params if p["in"] in ("path", "query", "header")] == ["id"]