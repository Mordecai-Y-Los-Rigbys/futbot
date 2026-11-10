"""GET /matches/{id}/behavior contra la base real (Postgres), con sesiones reales."""

import pytest

from app.api.ws_deps import get_match_runner
from app.domain.match import MatchStatus
from app.main import app
from app.models.team_member import MemberRole

pytestmark = pytest.mark.integration

CODE = "move(1, 0)"


class FakeRunner:
    def is_running(self, match_id):
        return True

    def queue_behavior(self, match_id, player_id, behavior):
        return True


def get_behavior(api, match_id, player_id):
    return api.get(f"/matches/{match_id}/behavior", params={"playerId": player_id})


@pytest.mark.parametrize("kind", ["league_match", "friendly_match"])
@pytest.mark.parametrize("user_id", [1, 2])
def test_player_gets_name_and_code_of_own_starter(
    request, kind, user_id, login_as, make_user, db_session
):
    match, teams = request.getfixturevalue(kind)
    starter = teams[user_id][0]
    r = get_behavior(login_as(make_user(user_id)), match.id, starter.player_id)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"name", "code"}
    assert body["code"] == "pass"


@pytest.mark.parametrize(
    "status", [MatchStatus.scheduled, MatchStatus.started, MatchStatus.finished]
)
def test_works_in_any_match_status_and_never_409(
    status, league_match, login_as, make_user, db_session
):
    match, teams = league_match
    match.status = status
    if status == MatchStatus.finished:  # ck_matches_result_iff_finished: terminó => hay resultado
        match.score_1, match.score_2 = 2, 1
    db_session.commit()
    r = get_behavior(login_as(make_user(1)), match.id, teams[1][1].player_id)
    assert r.status_code == 200


def test_after_a_put_behavior_returns_the_new_one(
    league_match, login_as, make_user, make_behaviors, client
):
    match, teams = league_match
    app.dependency_overrides[get_match_runner] = lambda: FakeRunner()
    new = make_behaviors(1, ["nuevo"], code=CODE)[0]
    api = login_as(make_user(1))
    starter = teams[1][0]
    body = {"playerId": starter.player_id, "behaviorId": new.id}
    put = api.put(f"/matches/{match.id}/behavior", json=body)
    assert put.status_code == 204

    r = get_behavior(api, match.id, starter.player_id)
    assert (r.json()["name"], r.json()["code"]) == ("nuevo", CODE)


def test_after_a_substitution_the_roles_swap(league_match, login_as, make_user, db_session):
    match, teams = league_match
    starter, substitute = teams[1][0], teams[1][3]
    api = login_as(make_user(1))
    assert get_behavior(api, match.id, substitute.player_id).status_code == 403
    # sustitución ya aplicada: el suplente toma el rol y el titular pasa a substitute
    starter.role, substitute.role = MemberRole.substitute, MemberRole.forward
    db_session.commit()

    assert get_behavior(api, match.id, substitute.player_id).status_code == 200
    r = get_behavior(api, match.id, starter.player_id)
    assert (r.status_code, r.json()["code"]) == (403, "playerNotStarter")


def test_league_spectator_is_403_not_a_player_and_never_sees_the_code(
    league_match, login_as, make_user
):
    match, teams = league_match
    api = login_as(make_user(3))
    assert api.get(f"/matches/{match.id}").status_code == 200  # puede ver el partido
    r = get_behavior(api, match.id, teams[1][0].player_id)
    assert (r.status_code, r.json()["code"]) == (403, "notAPlayerInMatch")
    assert "pass" not in r.text


def test_friendly_stranger_is_403_not_a_player(friendly_match, login_as, make_user):
    match, teams = friendly_match
    r = get_behavior(login_as(make_user(3)), match.id, teams[1][0].player_id)
    assert (r.status_code, r.json()["code"]) == (403, "notAPlayerInMatch")


@pytest.mark.parametrize("team, index", [(1, 3), (2, 0)])  # suplente propio / jugador del rival
def test_substitute_or_rival_player_is_403_not_starter(
    team, index, league_match, login_as, make_user
):
    match, teams = league_match
    r = get_behavior(login_as(make_user(1)), match.id, teams[team][index].player_id)
    assert (r.status_code, r.json()["code"]) == (403, "playerNotStarter")


def test_unknown_player_is_403_not_starter(league_match, login_as, make_user):
    match, _ = league_match
    r = get_behavior(login_as(make_user(1)), match.id, 999999)
    assert (r.status_code, r.json()["code"]) == (403, "playerNotStarter")


@pytest.mark.parametrize(
    "params, reason",
    [
        ({}, "required"),
        ({"playerId": ""}, "required"),
        ({"playerId": "abc"}, "invalidType"),
        ({"playerId": "1.5"}, "invalidType"),
        ({"playerId": "0"}, "outOfRange"),
        ({"playerId": "2147483648"}, "outOfRange"),
    ],
)
def test_invalid_player_id_is_400(params, reason, league_match, login_as, make_user):
    match, _ = league_match
    r = login_as(make_user(1)).get(f"/matches/{match.id}/behavior", params=params)
    assert r.status_code == 400 and r.json()["code"] == "invalidFields"
    assert r.json()["errors"] == [{"field": "playerId", "reason": reason}]


def test_non_player_with_invalid_player_id_is_400(league_match, login_as, make_user):
    match, _ = league_match
    r = login_as(make_user(3)).get(f"/matches/{match.id}/behavior", params={"playerId": "abc"})
    assert r.status_code == 400


def test_without_cookie_is_401(client, league_match):
    match, teams = league_match
    r = client.get(f"/matches/{match.id}/behavior?playerId={teams[1][0].player_id}")
    assert r.status_code == 401 and r.json()["code"] is None


def test_401_wins_over_404_and_400(client):
    assert client.get("/matches/abc/behavior?playerId=abc").status_code == 401


@pytest.mark.parametrize("bad", ["999999", "abc", "0", "-1", "1.5", "2147483648"])
def test_unknown_or_invalid_route_id_is_404_even_with_invalid_player_id(
    bad, login_as, make_user
):
    r = login_as(make_user(1)).get(f"/matches/{bad}/behavior?playerId=abc")
    assert r.status_code == 404
