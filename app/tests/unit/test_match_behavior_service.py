from unittest.mock import ANY, create_autospec

import pytest

from app.domain.behavior import BehaviorType
from app.domain.match import MatchStatus
from app.domain.team_member import MemberRole
from app.errors import ApiError
from app.repositories.behavior_abstract import AbstractBehaviorRepository, BehaviorData
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.team_abstract import AbstractTeamRepository, StarterData
from app.services.league_validation import INVALID_JSON
from app.services.match_behavior_service import MatchBehaviorService
from app.services.match_runner import MatchRunner
from app.simulation.behaviors.sandbox import CompiledBehavior

BODY = {"playerId": 3, "behaviorId": 7}


def match_data(status=MatchStatus.started):
    return MatchPlayersData(id=5, status=status, league_id=8, user_1_id=1, user_2_id=2)


@pytest.fixture()
def matches():
    m = create_autospec(AbstractMatchRepository, instance=True)
    m.get_players.return_value = match_data()
    return m


@pytest.fixture()
def teams():
    t = create_autospec(AbstractTeamRepository, instance=True)
    t.get_starters.return_value = [
        StarterData(player_id=3, role=MemberRole.forward, power=60, agility=60,
                    control=60, strength=60, speed=60, behavior_code="pass")
    ]
    return t


@pytest.fixture()
def behaviors():
    b = create_autospec(AbstractBehaviorRepository, instance=True)
    b.behavior_types.return_value = {7: BehaviorType.player_behavior}
    b.get_by_id.return_value = BehaviorData(id=7, user_id=1, name="b", code="pass")
    return b


@pytest.fixture()
def runner():
    r = create_autospec(MatchRunner, instance=True)
    r.is_running.return_value = True
    r.queue_behavior.return_value = True
    return r


@pytest.fixture()
def service(matches, teams, behaviors, runner):
    return MatchBehaviorService(matches, teams, behaviors, runner)


def error_of(service, user_id=1, body=BODY):
    with pytest.raises(ApiError) as exc:
        service.reassign(user_id, 5, body)
    return exc.value.status_code, exc.value.code


def test_valid_change_is_compiled_and_queued(service, teams, runner):
    service.reassign(1, 5, BODY)
    teams.get_starters.assert_called_once_with(5, 8, 1)  # usa la liga del partido
    runner.queue_behavior.assert_called_once_with(5, 3, ANY)
    assert isinstance(runner.queue_behavior.call_args.args[2], CompiledBehavior)


def test_missing_match_is_404_even_with_a_broken_body(service, matches, runner):
    matches.get_players.return_value = None
    assert error_of(service, body=INVALID_JSON) == (404, None)
    runner.queue_behavior.assert_not_called()


def test_broken_body_is_400_before_the_403(service):
    assert error_of(service, user_id=9, body=INVALID_JSON) == (400, "invalidFields")


def test_user_outside_the_match_is_403_even_if_it_did_not_start(service, matches):
    matches.get_players.return_value = match_data(MatchStatus.scheduled)
    assert error_of(service, user_id=9) == (403, "notAPlayerInMatch")


def test_player_that_is_not_a_starter_is_403(service):
    assert error_of(service, body={"playerId": 99, "behaviorId": 7}) == (403, "playerNotStarter")


@pytest.mark.parametrize(
    "status", [MatchStatus.scheduled, MatchStatus.finished, MatchStatus.cancelled]
)
def test_match_not_started_is_409(service, matches, status):
    matches.get_players.return_value = match_data(status)
    assert error_of(service) == (409, "matchNotInProgress")


def test_started_match_that_does_not_run_here_is_409(service, runner):
    runner.is_running.return_value = False
    assert error_of(service) == (409, "matchNotInProgress")


def test_not_in_progress_goes_before_not_owned(service, matches, behaviors):
    matches.get_players.return_value = match_data(MatchStatus.finished)
    behaviors.behavior_types.return_value = {}
    assert error_of(service) == (409, "matchNotInProgress")


def test_behavior_of_another_user_or_missing_is_409(service, behaviors, runner):
    behaviors.behavior_types.return_value = {}
    assert error_of(service) == (409, "playerOrBehaviorNotOwned")
    runner.queue_behavior.assert_not_called()


def test_coach_behavior_is_409(service, behaviors):
    behaviors.behavior_types.return_value = {7: BehaviorType.coach_behavior}
    assert error_of(service) == (409, "behaviorTypeMismatch")


def test_match_ending_during_the_request_is_409(service, runner):
    runner.queue_behavior.return_value = False
    assert error_of(service) == (409, "matchNotInProgress")