from datetime import datetime, timedelta, timezone
from itertools import combinations

import pytest

from app.domain.match import MatchStatus
from app.models.match import Match

pytestmark = pytest.mark.integration

START = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


@pytest.fixture()
def owner(create_user):
    return create_user("mgonzalez", "Boca Juniors FC")


def fixture_url(league):
    return f"/leagues/{league.id}/fixture"


@pytest.fixture()
def make_fixture(db_session):
    """Fixture de solo ida, como startLeague: un partido por par, sin superponerse."""

    def _make(league, users) -> list[Match]:
        matches = [
            Match(
                league_id=league.id,
                user_1_id=a.id,
                user_2_id=b.id,
                status=MatchStatus.scheduled,
                scheduled_at=START + timedelta(hours=i),
            )
            for i, (a, b) in enumerate(combinations(users, 2))
        ]
        db_session.add_all(reversed(matches))  # ids en orden inverso a las fechas
        db_session.commit()
        return matches

    return _make


@pytest.fixture()
def league_with_fixture(owner, create_user, make_league, add_participant, make_fixture):
    def _make(n=4, status="started", private=False):
        league = make_league(owner, status=status, private=private)
        users = [owner]
        for i in range(n - 1):
            user = create_user(f"rival{i}")
            add_participant(league, user)
            users.append(user)
        return league, users, make_fixture(league, users)

    return _make


# --- 401 / 404 ----------------------------------------------------------------


@pytest.mark.parametrize("league_id", ["1", "abc", "0", "2147483648", "99999"])
def test_without_session_returns_401_for_any_id(client, league_with_fixture, league_id):
    league_with_fixture()
    client.cookies.clear()

    response = client.get(f"/leagues/{league_id}/fixture")

    assert response.status_code == 401
    assert response.json()["code"] is None


def test_invalid_session_returns_401(client, league_with_fixture):
    league, _, _ = league_with_fixture()
    client.cookies.set("session_id", "invalid")
    assert client.get(fixture_url(league)).status_code == 401


@pytest.mark.parametrize("league_id", ["abc", "0", "-1", "1.5", "2147483648", "99999"])
def test_invalid_or_missing_id_returns_404(login_as, owner, league_with_fixture, league_id):
    league_with_fixture()

    response = login_as(owner).get(f"/leagues/{league_id}/fixture")

    assert response.status_code == 404
    assert response.json()["code"] is None


# --- 409 ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, code", [("preparation", "leagueNotStarted"), ("cancelled", "leagueCancelled")]
)
def test_league_without_fixture_returns_409(login_as, owner, make_league, status, code):
    league = make_league(owner, status=status)

    response = login_as(owner).get(fixture_url(league))

    assert response.status_code == 409
    assert response.json()["code"] == code


# --- orden de evaluación ------------------------------------------------------


def test_401_goes_before_404(client):
    client.cookies.clear()
    assert client.get("/leagues/abc/fixture").status_code == 401


def test_401_goes_before_403(client, league_with_fixture):
    league, _, _ = league_with_fixture(private=True)
    client.cookies.clear()
    assert client.get(fixture_url(league)).status_code == 401


def test_404_goes_before_403(login_as, create_user, league_with_fixture):
    league_with_fixture(private=True)
    assert login_as(create_user("extraño")).get("/leagues/99999/fixture").status_code == 404


def test_403_goes_before_409(login_as, owner, create_user, make_league):
    league = make_league(owner, status="preparation", private=True)

    response = login_as(create_user("extraño")).get(fixture_url(league))

    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"


# --- acceso -------------------------------------------------------------------


def test_public_league_is_readable_by_any_user(login_as, create_user, league_with_fixture):
    league, _, _ = league_with_fixture()
    assert login_as(create_user("extraño")).get(fixture_url(league)).status_code == 200


def test_private_league_is_readable_by_the_creator(login_as, owner, league_with_fixture):
    league, _, _ = league_with_fixture(private=True)
    assert login_as(owner).get(fixture_url(league)).status_code == 200


def test_private_league_is_readable_by_a_participant(login_as, league_with_fixture):
    league, users, _ = league_with_fixture(private=True)
    assert login_as(users[1]).get(fixture_url(league)).status_code == 200


def test_private_league_is_readable_by_a_session_that_unlocked_it(
    login_as, create_user, league_with_fixture
):
    league, _, _ = league_with_fixture(private=True)
    api = login_as(create_user("extraño"))

    assert api.post(f"/leagues/{league.id}/access", json={"password": "secret"}).status_code == 204
    assert api.get(fixture_url(league)).status_code == 200


def test_unlock_is_per_session(login_as, create_user, league_with_fixture):
    league, _, _ = league_with_fixture(private=True)
    stranger = create_user("extraño")
    unlocked_session, other_session = login_as(stranger), login_as(stranger)

    unlocked_session.post(f"/leagues/{league.id}/access", json={"password": "secret"})

    assert unlocked_session.get(fixture_url(league)).status_code == 200
    assert other_session.get(fixture_url(league)).status_code == 403


def test_private_league_without_access_returns_403(login_as, create_user, league_with_fixture):
    league, _, _ = league_with_fixture(private=True)

    response = login_as(create_user("extraño")).get(fixture_url(league))

    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"


def test_leaving_keeps_access_but_returns_409(
    login_as, owner, create_user, make_league, add_participant
):
    league = make_league(owner, private=True)
    member = create_user("participante")
    add_participant(league, member)
    api = login_as(member)

    assert api.post(f"/leagues/{league.id}/access").status_code == 204
    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    response = api.get(fixture_url(league))
    assert response.status_code == 409
    assert response.json()["code"] == "leagueNotStarted"


# --- contenido ----------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_returns_one_match_per_pair(login_as, owner, league_with_fixture, n):
    league, users, _ = league_with_fixture(n=n)

    body = login_as(owner).get(fixture_url(league)).json()

    assert len(body) == n * (n - 1) // 2
    pairs = {frozenset((m["club1"]["id"], m["club2"]["id"])) for m in body}
    assert pairs == {frozenset((a.id, b.id)) for a, b in combinations(users, 2)}


def test_is_ordered_by_scheduled_at(login_as, owner, league_with_fixture):
    league, _, matches = league_with_fixture(n=4)

    body = login_as(owner).get(fixture_url(league)).json()

    dates = [m["scheduledAt"] for m in body]
    assert dates == sorted(dates)
    assert [m["id"] for m in body] == [m.id for m in matches]


@pytest.mark.parametrize("status", ["started", "finished"])
def test_started_or_finished_league_returns_200(login_as, owner, league_with_fixture, status):
    league, _, _ = league_with_fixture(status=status)
    assert login_as(owner).get(fixture_url(league)).status_code == 200


def test_match_has_the_contract_fields(
    login_as, owner, create_user, make_league, add_participant, make_fixture
):
    league = make_league(owner, status="started")
    rival = create_user("rival", "River Plate")
    add_participant(league, rival)
    [match] = make_fixture(league, [owner, rival])

    [item] = login_as(owner).get(fixture_url(league)).json()

    assert item.keys() == {
        "id", "leagueId", "name", "status", "club1", "club2", "scheduledAt", "createdAt", "result"
    }
    assert item["id"] == match.id
    assert item["leagueId"] == league.id
    assert item["name"] is None
    assert item["status"] == "scheduled"
    assert item["club1"] == {
        "id": owner.id, "username": "mgonzalez", "name": "Boca Juniors FC", "avatar": owner.avatar
    }
    assert item["club2"] == {
        "id": rival.id, "username": "rival", "name": "River Plate", "avatar": rival.avatar
    }
    assert item["scheduledAt"] == "2026-01-01T18:00:00Z"
    assert item["createdAt"].endswith("Z")
    assert item["result"] is None


def test_finished_match_has_result(login_as, owner, league_with_fixture, db_session):
    league, _, matches = league_with_fixture(n=3)
    first = matches[0]
    first.status = MatchStatus.finished
    first.score_1, first.score_2 = 2, 1
    db_session.commit()

    body = login_as(owner).get(fixture_url(league)).json()

    assert body[0]["status"] == "finished"
    assert body[0]["result"] == {"score1": 2, "score2": 1, "penalties": None}
    assert all(m["result"] is None for m in body[1:])


def test_does_not_include_other_leagues_or_friendlies(
    login_as, owner, create_user, make_league, make_fixture, league_with_fixture, db_session
):
    league, _, matches = league_with_fixture(n=3)
    other = make_league(owner, "Otra", status="started")
    make_fixture(other, [owner, create_user("ajeno")])
    db_session.add(Match(league_id=None, user_1_id=owner.id, status=MatchStatus.scheduled))
    db_session.commit()

    body = login_as(owner).get(fixture_url(league)).json()

    assert {m["id"] for m in body} == {m.id for m in matches}
