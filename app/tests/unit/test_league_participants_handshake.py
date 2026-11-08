from datetime import datetime, timedelta, timezone

import pytest

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.services.league_participants_handshake import LeagueParticipantsHandshakeService
from app.tests.unit.league_participants_fakes import CREATOR_ID, ORIGIN, FakeLeagues, FakeSessions

USER_ID = 8  # un usuario cualquiera, que no es el creador


@pytest.fixture()
def sessions():
    repo = FakeSessions()
    repo.add("creator-session", CREATOR_ID)
    repo.add("user-session", USER_ID)
    return repo


@pytest.fixture()
def leagues():
    repo = FakeLeagues()
    repo.add(1)  # pública, en preparación
    repo.add(2, private=True)
    return repo


@pytest.fixture()
def service(sessions, leagues):
    return LeagueParticipantsHandshakeService([ORIGIN], sessions, leagues, leagues)


def failure(service, origin=ORIGIN, session_id="user-session", league_id="1") -> tuple[int, str]:
    with pytest.raises(ApiError) as exc:
        service.authorize(origin, session_id, league_id)
    return exc.value.status_code, exc.value.code


# --- aceptado -----------------------------------------------------------------


def test_public_league_in_preparation_is_open_to_any_authenticated_user(service):
    grant = service.authorize(ORIGIN, "user-session", "1")
    assert (grant.user_id, grant.league_id, grant.session_id) == (USER_ID, 1, "user-session")


def test_grant_carries_the_session_expiry(service, sessions):
    expires = datetime.now(timezone.utc) + timedelta(hours=3)
    sessions.add("short", USER_ID, expires_at=expires)
    assert service.authorize(ORIGIN, "short", "1").session_expires_at == expires


def test_private_league_is_open_to_its_creator(service):
    assert service.authorize(ORIGIN, "creator-session", "2").user_id == CREATOR_ID


def test_private_league_is_open_to_a_participant(service, leagues):
    leagues.join(2, USER_ID)
    assert service.authorize(ORIGIN, "user-session", "2").user_id == USER_ID


def test_private_league_is_open_to_a_session_that_unlocked_it(service, leagues):
    leagues.unlock("user-session", 2)
    assert service.authorize(ORIGIN, "user-session", "2").user_id == USER_ID


# --- cada rechazo -------------------------------------------------------------


@pytest.mark.parametrize("origin", [None, "", "http://evil.com", ORIGIN + "/", "http://localhost"])
def test_missing_or_foreign_origin_is_403_origin_not_allowed(service, origin):
    assert failure(service, origin=origin) == (403, "originNotAllowed")


@pytest.mark.parametrize("session_id", [None, "", "no-existe", "x" * 200])
def test_missing_or_invalid_session_is_401_session_invalid(service, session_id):
    assert failure(service, session_id=session_id) == (401, "sessionInvalid")


@pytest.mark.parametrize("league_id", ["999", "0", "-1", "abc", "1.5", "2147483648", "٣"])
def test_unknown_league_or_invalid_id_is_404_league_not_found(service, league_id):
    assert failure(service, league_id=league_id) == (404, "leagueNotFound")


def test_private_league_without_access_is_403_league_access_required(service):
    assert failure(service, league_id="2") == (403, "leagueAccessRequired")


def test_unlock_of_another_session_does_not_count(service, leagues):
    leagues.unlock("creator-session", 2)
    assert failure(service, league_id="2") == (403, "leagueAccessRequired")


@pytest.mark.parametrize(
    "status", [LeagueStatus.started, LeagueStatus.cancelled, LeagueStatus.finished]
)
def test_league_not_in_preparation_is_409(service, leagues, status):
    leagues.set_status(1, status)
    assert failure(service) == (409, "leagueNotInPreparation")


# --- orden de precedencia -----------------------------------------------------


def test_origin_is_checked_before_the_session(service):
    assert failure(service, origin=None, session_id=None, league_id="abc") == (
        403,
        "originNotAllowed",
    )


def test_session_is_checked_before_the_league(service):
    assert failure(service, session_id="no-existe", league_id="999") == (401, "sessionInvalid")


def test_league_not_found_beats_access_and_state(service):
    assert failure(service, league_id="999") == (404, "leagueNotFound")


def test_access_is_checked_before_the_state(service, leagues):
    leagues.set_status(2, LeagueStatus.started)
    assert failure(service, league_id="2") == (403, "leagueAccessRequired")


def test_the_session_is_not_looked_up_when_the_origin_fails(leagues):
    class ExplodingSessions:
        def get_valid(self, session_id):
            raise AssertionError("no debería consultar la sesión")

    service = LeagueParticipantsHandshakeService([ORIGIN], ExplodingSessions(), leagues, leagues)
    assert failure(service, origin="http://evil.com") == (403, "originNotAllowed")
