from unittest.mock import create_autospec

import pytest

from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    FirstSubstitutionData,
)
from app.services.substitution_service import SubstitutionService


@pytest.fixture()
def matches():
    m = create_autospec(AbstractMatchRepository, instance=True)
    m.get_players.return_value = MatchPlayersData(
        id=5, status=MatchStatus.started, user_1_id=1, user_2_id=2
    )
    return m


@pytest.fixture()
def subs():
    s = create_autospec(AbstractSubstitutionRepository, instance=True)
    s.list_first_per_team.return_value = []
    return s


def error_of(service, user_id=1):
    with pytest.raises(ApiError) as e:
        service.get_next(user_id, 5)
    return e.value.status_code, e.value.code


def test_nonexistent_match_is_404(matches, subs):
    matches.get_players.return_value = None
    assert error_of(SubstitutionService(matches, subs)) == (404, None)
    subs.list_first_per_team.assert_not_called()


def test_user_outside_the_match_is_403_even_if_not_started(matches, subs):
    matches.get_players.return_value = MatchPlayersData(
        id=5, status=MatchStatus.scheduled, user_1_id=1, user_2_id=2
    )
    assert error_of(SubstitutionService(matches, subs), user_id=9) == (403, None)


@pytest.mark.parametrize(
    "status", [MatchStatus.scheduled, MatchStatus.finished, MatchStatus.cancelled]
)
def test_not_started_is_409(matches, subs, status):
    matches.get_players.return_value = MatchPlayersData(
        id=5, status=status, user_1_id=1, user_2_id=2
    )
    assert error_of(SubstitutionService(matches, subs)) == (409, "matchNotStarted")


def test_maps_each_team_and_null_for_the_one_without_substitutions(matches, subs):
    subs.list_first_per_team.return_value = [
        FirstSubstitutionData(user_id=2, starter_name="A", substitute_name="B")
    ]
    out = SubstitutionService(matches, subs).get_next(1, 5)
    assert out.club1 is None
    assert (out.club2.starter_name, out.club2.substitute_name) == ("A", "B")


def test_same_result_for_both_users(matches, subs):
    subs.list_first_per_team.return_value = [
        FirstSubstitutionData(user_id=2, starter_name="C2", substitute_name="D2"),
        FirstSubstitutionData(user_id=1, starter_name="C1", substitute_name="D1"),
    ]
    s = SubstitutionService(matches, subs)

    for user_id in (1, 2):
        out = s.get_next(user_id, 5)
        # club1 siempre es user_1 y club2 siempre user_2, sea quien sea el que consulta.
        assert (out.club1.starter_name, out.club1.substitute_name) == ("C1", "D1")
        assert (out.club2.starter_name, out.club2.substitute_name) == ("C2", "D2")
    assert s.get_next(1, 5) == s.get_next(2, 5)