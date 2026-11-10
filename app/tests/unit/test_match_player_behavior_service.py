from unittest.mock import create_autospec

import pytest

from app.domain.behavior import BehaviorType
from app.domain.match import MatchStatus
from app.domain.team_member import MemberRole
from app.errors import ApiError, ValidationApiError
from app.repositories.behavior_abstract import AbstractBehaviorRepository, BehaviorData
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.team_abstract import (
    AbstractTeamRepository,
    MatchTeamData,
    TeamBehaviorData,
    TeamMemberData,
)
from app.services.match_player_behavior_service import MatchPlayerBehaviorService

ROLES = [
    MemberRole.forward,
    MemberRole.midfield,
    MemberRole.defense,
    MemberRole.substitute,
    MemberRole.substitute,
    MemberRole.substitute,
]


def team_data():
    # jugadores 10..15: 10-12 titulares, 13-15 suplentes; el behavior de 10 es el 100
    return MatchTeamData(
        members=[
            TeamMemberData(
                player_id=10 + i,
                name=f"J{i}",
                role=role,
                behavior=TeamBehaviorData(
                    id=100 + i, name=f"b{i}", type=BehaviorType.player_behavior
                ),
            )
            for i, role in enumerate(ROLES)
        ],
        coach_behavior=None,
    )


def match_data(status=MatchStatus.started, user_2_id=2):
    return MatchPlayersData(id=5, status=status, league_id=8, user_1_id=1, user_2_id=user_2_id)


@pytest.fixture()
def matches():
    m = create_autospec(AbstractMatchRepository, instance=True)
    m.get_players.return_value = match_data()
    return m


@pytest.fixture()
def teams():
    t = create_autospec(AbstractTeamRepository, instance=True)
    t.get_match_team.return_value = team_data()
    return t


@pytest.fixture()
def behaviors():
    b = create_autospec(AbstractBehaviorRepository, instance=True)
    b.get_by_id.side_effect = lambda bid: BehaviorData(
        id=bid, user_id=1, name=f"b{bid - 100}", code=f"codigo {bid}"
    )
    return b


@pytest.fixture()
def service(matches, teams, behaviors):
    return MatchPlayerBehaviorService(matches, teams, behaviors)


def error_of(service, user_id=1, raw="10"):
    with pytest.raises(ApiError) as exc:
        service.get_behavior(user_id, 5, raw)
    return exc.value


def test_starter_gets_name_and_code(service, teams, behaviors):
    result = service.get_behavior(1, 5, "10")
    assert (result.name, result.code) == ("b0", "codigo 100")
    teams.get_match_team.assert_called_once_with(5, 8, 1)  # usa la liga del partido
    behaviors.get_by_id.assert_called_once_with(100)


@pytest.mark.parametrize("status", list(MatchStatus))
def test_works_in_any_match_status(service, matches, status):
    matches.get_players.return_value = match_data(status)
    assert service.get_behavior(1, 5, "11").code == "codigo 101"


def test_creator_of_friendly_without_rival_is_allowed(service, matches):
    matches.get_players.return_value = match_data(user_2_id=None)
    assert service.get_behavior(1, 5, "10").name == "b0"


def test_does_not_modify_anything(service, teams):
    service.get_behavior(1, 5, "10")
    assert not teams.set_behavior.called


def test_missing_match_is_404(service, matches):
    matches.get_players.return_value = None
    err = error_of(service)
    assert (err.status_code, err.code) == (404, None)


def test_404_wins_over_400(service, matches):
    matches.get_players.return_value = None
    assert error_of(service, raw="abc").status_code == 404


@pytest.mark.parametrize(
    "raw, reason",
    [
        (None, "required"),
        ("", "required"),
        ("abc", "invalidType"),
        ("1.5", "invalidType"),
        ("0", "outOfRange"),
        ("-1", "outOfRange"),
        ("2147483648", "outOfRange"),
    ],
)
def test_invalid_player_id_is_400_with_its_reason(service, raw, reason):
    err = error_of(service, raw=raw)
    assert isinstance(err, ValidationApiError)
    assert err.errors == [{"field": "playerId", "reason": reason}]


def test_non_player_with_invalid_player_id_is_400_not_403(service):
    assert error_of(service, user_id=3, raw="abc").status_code == 400


def test_non_player_with_valid_player_id_is_403_not_a_player(service, teams):
    err = error_of(service, user_id=3, raw="10")
    assert (err.status_code, err.code) == (403, "notAPlayerInMatch")
    teams.get_match_team.assert_not_called()  # no hay equipo contra el cual evaluar


def test_substitute_is_403_not_starter(service, behaviors):
    err = error_of(service, raw="13")
    assert (err.status_code, err.code) == (403, "playerNotStarter")
    behaviors.get_by_id.assert_not_called()


@pytest.mark.parametrize("raw", ["999", "20"])  # inexistente / de otro equipo
def test_unknown_or_foreign_player_is_403_not_starter(service, raw):
    err = error_of(service, raw=raw)
    assert (err.status_code, err.code) == (403, "playerNotStarter")


def test_reflects_the_current_team(service, teams):
    # sustitución aplicada: el 13 entra como titular y el 10 sale
    team = team_data()
    team.members[0].role = MemberRole.substitute
    team.members[3].role = MemberRole.forward
    teams.get_match_team.return_value = team
    assert service.get_behavior(1, 5, "13").code == "codigo 103"
    assert error_of(service, raw="10").code == "playerNotStarter"
