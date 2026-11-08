import pytest

from app.api.ws_deps import get_match_runner
from app.domain.behavior import BehaviorType
from app.main import app
from app.models.behavior import Behavior

pytestmark = pytest.mark.integration


class FakeRunner:
    def __init__(self):
        self.queued = []

    def is_running(self, match_id):
        return True

    def queue_behavior(self, match_id, player_id, behavior):
        self.queued.append((match_id, player_id))
        return True


@pytest.fixture()
def runner(client):
    fake = FakeRunner()
    app.dependency_overrides[get_match_runner] = lambda: fake
    return fake


def put(api, match, player_id, behavior_id):
    body = {"playerId": player_id, "behaviorId": behavior_id}
    return api.put(f"/matches/{match.id}/behavior", json=body)


@pytest.mark.parametrize("kind", ["league_match", "friendly_match"])
def test_starter_change_is_204_queued_and_saved_in_the_team(
    request, kind, login_as, make_user, make_behaviors, runner, db_session
):
    match, teams = request.getfixturevalue(kind)
    new = make_behaviors(1, ["nuevo"], code="pass")[0]
    starter, teammate = teams[1][0], teams[1][1]

    resp = put(login_as(make_user(1)), match, starter.player_id, new.id)

    assert resp.status_code == 204
    assert runner.queued == [(match.id, starter.player_id)]
    db_session.expire_all()
    assert starter.behavior_id == new.id
    assert teammate.behavior_id != new.id


@pytest.mark.parametrize("team, index", [(1, 3), (2, 0)])
def test_player_that_is_not_my_starter_is_403(
    team, index, league_match, login_as, make_user, make_behaviors, runner
):
    match, teams = league_match
    new = make_behaviors(1, ["nuevo"], code="pass")[0]
    r = put(login_as(make_user(1)), match, teams[team][index].player_id, new.id)
    assert (r.status_code, r.json()["code"]) == (403, "playerNotStarter")


def test_behavior_of_the_rival_is_409(league_match, login_as, make_user, make_behaviors, runner):
    match, teams = league_match
    rival_behavior = make_behaviors(2, ["ajeno"], code="pass")[0]
    r = put(login_as(make_user(1)), match, teams[1][0].player_id, rival_behavior.id)
    assert (r.status_code, r.json()["code"]) == (409, "playerOrBehaviorNotOwned")


@pytest.mark.parametrize(
    "owner, code", [(1, "behaviorTypeMismatch"), (2, "playerOrBehaviorNotOwned")]
)
def test_coach_behavior_is_409(owner, code, league_match, login_as, make_user, db_session, runner):
    match, teams = league_match
    coach = Behavior(user_id=owner, name="dt", code="pass", type=BehaviorType.coach_behavior)
    db_session.add(coach)
    db_session.commit()
    r = put(login_as(make_user(1)), match, teams[1][0].player_id, coach.id)
    assert (r.status_code, r.json()["code"]) == (409, code)


def test_started_match_that_does_not_run_here_is_409(
    league_match, login_as, make_user, make_behaviors
):
    match, teams = league_match
    new = make_behaviors(1, ["nuevo"], code="pass")[0]
    r = put(login_as(make_user(1)), match, teams[1][0].player_id, new.id)
    assert (r.status_code, r.json()["code"]) == (409, "matchNotInProgress")
