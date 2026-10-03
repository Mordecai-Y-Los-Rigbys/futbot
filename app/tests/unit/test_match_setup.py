"""MatchSetupService con repositories fake en memoria (sin base de datos)."""

import pytest

from app.domain.team_member import MemberRole
from app.repositories.league_abstract import AbstractLeagueRepository
from app.repositories.match_abstract import AbstractMatchRepository, MatchSetupData
from app.repositories.team_abstract import AbstractTeamRepository, StarterData
from app.services.match_setup_service import MatchSetupService
from app.simulation.constants import STARTER_ROLES, FRIENDLY_MATCH_DURATION
from app.tests.unit.match_ws_fakes import FakeMatchRepo


def starter(player_id: int, role: str, code: str = "pass") -> StarterData:
    return StarterData(
        player_id=player_id, role=role, power=60, agility=60, control=60,
        strength=60, speed=60, behavior_code=code,
    )


def full_team(first_id: int) -> list[StarterData]:
    return [starter(first_id + i, r.value) for i, r in enumerate(STARTER_ROLES)]

class FakeLeagues(AbstractLeagueRepository):
    def __init__(self, durations=None):
        self.durations = durations or {}
        self.calls = []

    def get_match_duration_minutes(self, league_id):
        self.calls.append(league_id)
        return self.durations.get(league_id)

    def list_page(self, name, offset, limit):
        raise NotImplementedError

    def create(self, data):
        raise NotImplementedError

class FakeTeams(AbstractTeamRepository):
    def __init__(self, starters=None):
        self.starters = starters or {}  # {user_id: [StarterData]}
        self.calls = []

    def get_starters(self, match_id, league_id, user_id):
        self.calls.append((match_id, league_id, user_id))
        return self.starters.get(user_id, [])

    def owned_player_ids(self, user_id, ids):
        raise NotImplementedError

    def owned_behavior_ids(self, user_id, ids):
        raise NotImplementedError


def setup_data(league_id=None, user_2_id=2, club_2="Club Dos") -> MatchSetupData:
    return MatchSetupData(
        id=1, league_id=league_id, user_1_id=1, user_2_id=user_2_id,
        club_1_name="Club Uno", club_2_name=club_2,
    )



def build(match=None, durations=None, starters=None):
    matches = FakeMatchRepo()
    if match:
        matches.setups[1] = match
    leagues = FakeLeagues(durations)
    teams = FakeTeams(starters if starters is not None else {1: full_team(10), 2: full_team(20)})
    return MatchSetupService(matches, leagues, teams), leagues, teams


def test_league_match_uses_the_league_duration_and_league_teams():
    service, leagues, teams = build(setup_data(league_id=5), durations={5: 2})
    setup = service.load_match_setup(1)

    assert setup.duration_seconds == 120
    assert leagues.calls == [5]
    assert teams.calls == [(1, 5, 1), (1, 5, 2)]
    assert (setup.club_1_name, setup.club_2_name) == ("Club Uno", "Club Dos")


def test_friendly_uses_the_fixed_duration_and_never_asks_the_league():
    service, leagues, teams = build(setup_data(league_id=None))
    setup = service.load_match_setup(1)

    assert setup.duration_seconds == FRIENDLY_MATCH_DURATION * 60
    assert leagues.calls == []
    assert teams.calls == [(1, None, 1), (1, None, 2)]


def test_each_team_has_three_starters_with_their_behaviors():
    service, _, _ = build(setup_data())
    setup = service.load_match_setup(1)

    for team, first_id in ((setup.team_1, 10), (setup.team_2, 20)):
        assert {p.role for p in team.players} == set(STARTER_ROLES)
        assert set(team.behaviors) == set(STARTER_ROLES)
        assert {p.player_id for p in team.players} == {first_id, first_id + 1, first_id + 2}


def test_unknown_match_is_a_lookup_error():
    service, _, _ = build(match=None)
    with pytest.raises(LookupError):
        service.load_match_setup(1)


def test_match_without_rival_is_a_lookup_error():
    service, _, _ = build(setup_data(user_2_id=None, club_2=None))
    with pytest.raises(LookupError):
        service.load_match_setup(1)


def test_league_that_does_not_exist_is_a_lookup_error():
    service, _, _ = build(setup_data(league_id=5), durations={})
    with pytest.raises(LookupError):
        service.load_match_setup(1)


def test_team_without_starters_is_an_error():
    service, _, _ = build(setup_data(), starters={1: full_team(10), 2: []})
    with pytest.raises(ValueError):
        service.load_match_setup(1)


def test_team_with_fewer_than_three_starters_is_an_error():
    service, _, _ = build(setup_data(), starters={1: full_team(10)[:2], 2: full_team(20)})
    with pytest.raises(ValueError):
        service.load_match_setup(1)


def test_a_substitute_among_the_starters_is_an_error():
    bad = full_team(10)[:2] + [starter(99, MemberRole.substitute.value)]
    service, _, _ = build(setup_data(), starters={1: bad, 2: full_team(20)})
    with pytest.raises(ValueError):
        service.load_match_setup(1)


def test_a_repeated_role_is_an_error():
    bad = full_team(10)[:2] + [starter(99, STARTER_ROLES[0].value)]
    service, _, _ = build(setup_data(), starters={1: bad, 2: full_team(20)})
    with pytest.raises(ValueError):
        service.load_match_setup(1)