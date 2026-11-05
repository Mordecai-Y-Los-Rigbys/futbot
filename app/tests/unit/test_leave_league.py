import pytest

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.repositories.league_abstract import LeagueLeaveInfo
from app.services.league_service import LeagueService

USER_ID = 7  # el usuario de la sesión "valid-session" de la fixture `api`
OTHER_ID = 99


class FakeNotifier:
    def __init__(self):
        self.calls: list[int] = []

    def participants_changed(self, league_id: int) -> None:
        self.calls.append(league_id)


@pytest.fixture()
def notifier():
    return FakeNotifier()


@pytest.fixture()
def leave_service(fake_repo, fake_players, fake_behaviors, notifier):
    return LeagueService(fake_repo, fake_players, fake_behaviors, notifier=notifier)


@pytest.fixture()
def setup_league(fake_repo):
    """Crea la liga 5 con creador OTHER_ID y al usuario 7 como participante."""

    def _setup(status=LeagueStatus.preparation, creator_id=OTHER_ID, member=True):
        fake_repo.leave_info[5] = LeagueLeaveInfo(status=status, creator_id=creator_id)
        fake_repo.participants.add((5, creator_id))
        if member:
            fake_repo.participants.add((5, USER_ID))

    return _setup


# ---------- service ----------


def test_leave_success_removes_participation(leave_service, fake_repo, setup_league):
    setup_league()
    leave_service.leave_league(USER_ID, "5")
    assert fake_repo.removed == [(5, USER_ID)]
    assert (5, USER_ID) not in fake_repo.participants
    assert (5, OTHER_ID) in fake_repo.participants


def test_leave_not_participating(leave_service, fake_repo, setup_league):
    setup_league(member=False)
    with pytest.raises(ApiError) as exc:
        leave_service.leave_league(USER_ID, "5")
    assert (exc.value.status_code, exc.value.code) == (409, "notParticipating")
    assert fake_repo.removed == []


def test_leave_creator_is_rejected(leave_service, fake_repo, setup_league):
    setup_league(creator_id=USER_ID, member=False)
    with pytest.raises(ApiError) as exc:
        leave_service.leave_league(USER_ID, "5")
    assert (exc.value.status_code, exc.value.code) == (409, "isCreator")
    assert fake_repo.removed == []


@pytest.mark.parametrize(
    "status", [LeagueStatus.started, LeagueStatus.finished, LeagueStatus.cancelled]
)
def test_leave_not_in_preparation(leave_service, fake_repo, setup_league, status):
    setup_league(status=status)
    with pytest.raises(ApiError) as exc:
        leave_service.leave_league(USER_ID, "5")
    assert (exc.value.status_code, exc.value.code) == (409, "notInPreparation")
    assert fake_repo.removed == []


def test_leave_nonexistent_league(leave_service, fake_repo):
    with pytest.raises(ApiError) as exc:
        leave_service.leave_league(USER_ID, "5")
    assert (exc.value.status_code, exc.value.code) == (404, None)
    assert fake_repo.removed == []


@pytest.mark.parametrize("raw", ["abc", "0", "-1", "1.5", "2147483648", "", "１２"])
def test_leave_invalid_id_is_404(leave_service, fake_repo, raw):
    with pytest.raises(ApiError) as exc:
        leave_service.leave_league(USER_ID, raw)
    assert (exc.value.status_code, exc.value.code) == (404, None)
    assert fake_repo.removed == []


def test_notifier_called_only_on_success(leave_service, notifier, setup_league):
    setup_league()
    leave_service.leave_league(USER_ID, "5")
    assert notifier.calls == [5]


@pytest.mark.parametrize("scenario", ["not_member", "creator", "started", "missing", "bad_id"])
def test_notifier_not_called_on_failure(leave_service, notifier, setup_league, scenario):
    raw = "5"
    if scenario == "not_member":
        setup_league(member=False)
    elif scenario == "creator":
        setup_league(creator_id=USER_ID, member=False)
    elif scenario == "started":
        setup_league(status=LeagueStatus.started)
    elif scenario == "bad_id":
        raw = "abc"
    with pytest.raises(ApiError):
        leave_service.leave_league(USER_ID, raw)
    assert notifier.calls == []


def test_service_without_notifier_still_works(
    fake_repo, fake_players, fake_behaviors, setup_league
):
    setup_league()
    service = LeagueService(fake_repo, fake_players, fake_behaviors)  # sin notifier
    service.leave_league(USER_ID, "5")
    assert fake_repo.removed == [(5, USER_ID)]


# ---------- endpoint (controller) ----------


def test_endpoint_requires_auth(api, setup_league):
    setup_league()
    resp = api.delete("/leagues/5/participants/me")  # sin cookie
    assert resp.status_code == 401
    assert resp.json()["code"] is None


def test_endpoint_401_goes_before_404(api):
    resp = api.delete("/leagues/999/participants/me")  # sin cookie y liga inexistente
    assert resp.status_code == 401


def test_endpoint_success_is_204_without_body(auth_api, fake_repo, setup_league):
    setup_league()
    resp = auth_api.delete("/leagues/5/participants/me")
    assert resp.status_code == 204
    assert resp.content == b""
    assert fake_repo.removed == [(5, USER_ID)]


@pytest.mark.parametrize("raw", ["abc", "0", "99999999999"])
def test_endpoint_invalid_id_is_404_never_400_or_422(auth_api, raw):
    resp = auth_api.delete(f"/leagues/{raw}/participants/me")
    assert resp.status_code == 404
    assert resp.json()["code"] is None


def test_endpoint_nonexistent_league_is_404(auth_api):
    assert auth_api.delete("/leagues/5/participants/me").status_code == 404


def test_endpoint_404_goes_before_409(auth_api, fake_repo):
    # Id inválido: gana el 404 aunque el usuario no participe en nada
    assert auth_api.delete("/leagues/abc/participants/me").status_code == 404
    assert fake_repo.removed == []


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"member": False}, "notParticipating"),
        ({"creator_id": USER_ID, "member": False}, "isCreator"),
        ({"status": LeagueStatus.started}, "notInPreparation"),
    ],
)
def test_endpoint_409_codes(auth_api, setup_league, kwargs, code):
    setup_league(**kwargs)
    resp = auth_api.delete("/leagues/5/participants/me")
    assert resp.status_code == 409
    assert resp.json()["code"] == code


# ---------- contrato ----------


def test_openapi_leave_league_matches_contract():
    from app.main import app

    spec = app.openapi()
    operation = spec["paths"]["/leagues/{id}/participants/me"]["delete"]

    assert operation["operationId"] == "leaveLeague"
    assert {"204", "401", "404", "409"} <= set(operation["responses"])
    assert "content" not in operation["responses"]["204"]  # 204 sin body

    codes = spec["components"]["schemas"]["LeaveLeagueConflict"]["properties"]["code"]["enum"]
    assert codes == ["notInPreparation", "notParticipating", "isCreator"]