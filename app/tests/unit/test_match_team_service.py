from unittest.mock import create_autospec

import pytest

from app.domain.behavior import BehaviorType
from app.domain.match import MatchStatus
from app.domain.team_member import MemberRole
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.team_abstract import (
    AbstractTeamRepository,
    MatchTeamData,
    TeamBehaviorData,
    TeamMemberData,
)
from app.services.match_team_service import MatchTeamService

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


def team_data(coach=True):
    members = [
        TeamMemberData(
            player_id=10 + i,
            name=f"J{i}",
            role=MemberRole(role),
            behavior=TeamBehaviorData(
                id=100 + i, name=f"B{i}", type=BehaviorType.player_behavior
            ),
        )
        for i, role in enumerate(ROLES)
    ]
    dt = TeamBehaviorData(id=9, name="DT", type=BehaviorType.coach_behavior) if coach else None
    return MatchTeamData(members=members, coach_behavior=dt)


@pytest.fixture()
def matches():
    m = create_autospec(AbstractMatchRepository, instance=True)
    m.get_players.return_value = MatchPlayersData(
        id=5, league_id=None, status=MatchStatus.started, user_1_id=1, user_2_id=2
    )
    return m


@pytest.fixture()
def teams():
    t = create_autospec(AbstractTeamRepository, instance=True)
    t.get_match_team.return_value = team_data()
    return t


@pytest.fixture()
def service(matches, teams):
    return MatchTeamService(matches, teams)


def error_of(service, user_id=1, match_id=5):
    with pytest.raises(ApiError) as e:
        service.get_team(user_id, match_id)
    return e.value.status_code, e.value.code


def test_nonexistent_match_is_404_and_reads_no_team(service, matches, teams):
    matches.get_players.return_value = None
    assert error_of(service) == (404, None)
    teams.get_match_team.assert_not_called()


def test_user_outside_the_match_is_403_not_a_player(service, teams):
    assert error_of(service, user_id=9) == (403, "notAPlayerInMatch")
    teams.get_match_team.assert_not_called()


def test_spectator_of_a_league_match_is_403_not_a_player(service, matches, teams):
    # Un espectador con acceso a la liga puede ver el partido, pero no su equipo.
    matches.get_players.return_value = MatchPlayersData(
        id=5, league_id=3, status=MatchStatus.started, user_1_id=1, user_2_id=2
    )
    assert error_of(service, user_id=9) == (403, "notAPlayerInMatch")
    teams.get_match_team.assert_not_called()


@pytest.mark.parametrize("user_id", [1, 2])
def test_each_player_gets_only_their_own_team(service, teams, user_id):
    service.get_team(user_id, 5)
    teams.get_match_team.assert_called_once_with(5, None, user_id)


def test_league_match_passes_the_league_id(service, matches, teams):
    matches.get_players.return_value = MatchPlayersData(
        id=5, league_id=3, status=MatchStatus.started, user_1_id=1, user_2_id=2
    )
    service.get_team(2, 5)
    teams.get_match_team.assert_called_once_with(5, 3, 2)


def test_friendly_creator_without_rival_gets_200(service, matches, teams):
    matches.get_players.return_value = MatchPlayersData(
        id=5, league_id=None, status=MatchStatus.scheduled, user_1_id=1, user_2_id=None
    )
    out = service.get_team(1, 5)
    assert len(out.members) == 6
    teams.get_match_team.assert_called_once_with(5, None, 1)


def test_a_stranger_cannot_use_the_missing_rival_slot(service, matches):
    matches.get_players.return_value = MatchPlayersData(
        id=5, league_id=None, status=MatchStatus.scheduled, user_1_id=1, user_2_id=None
    )
    assert error_of(service, user_id=9) == (403, "notAPlayerInMatch")


def test_response_keeps_starters_first_then_substitutes(service):
    out = service.get_team(1, 5)
    assert [m.role.value for m in out.members] == ROLES
    first = out.members[0]
    assert (first.player_id, first.name) == (10, "J0")
    assert (first.behavior.id, first.behavior.name, first.behavior.type) == (
        100,
        "B0",
        BehaviorType.player_behavior,
    )


def test_coach_behavior_is_included(service):
    out = service.get_team(1, 5)
    assert (out.coach_behavior.id, out.coach_behavior.name, out.coach_behavior.type) == (
        9,
        "DT",
        BehaviorType.coach_behavior,
    )


def test_coach_behavior_is_null_without_dt(service, teams):
    teams.get_match_team.return_value = team_data(coach=False)
    assert service.get_team(1, 5).coach_behavior is None


@pytest.mark.parametrize("status", list(MatchStatus))
def test_there_is_no_409_in_any_match_status(service, matches, status):
    matches.get_players.return_value = MatchPlayersData(
        id=5, league_id=None, status=status, user_1_id=1, user_2_id=2
    )
    assert len(service.get_team(1, 5).members) == 6
