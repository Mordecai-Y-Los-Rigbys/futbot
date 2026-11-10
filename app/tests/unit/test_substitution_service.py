from unittest.mock import create_autospec

import pytest

from app.domain.match import MatchStatus
from app.errors import ApiError
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.substitution_abstract import (
    AbstractSubstitutionRepository,
    SubstitutionData,
)
from app.repositories.team_abstract import AbstractTeamRepository
from app.services.match_progress import MatchProgress, MatchProgressReader
from app.services.substitution_service import SubstitutionService
from app.simulation.match_rules import Phase


@pytest.fixture()
def matches():
    m = create_autospec(AbstractMatchRepository, instance=True)
    m.get_players.return_value = MatchPlayersData(
        id=5, status=MatchStatus.started, league_id=None, user_1_id=1, user_2_id=2
    )
    return m


@pytest.fixture()
def subs():
    s = create_autospec(AbstractSubstitutionRepository, instance=True)
    s.list_by_match.return_value = []
    s.list_applied_by_match.return_value = []
    return s


@pytest.fixture()
def progress():
    p = create_autospec(MatchProgressReader, instance=True)
    p.progress.return_value = MatchProgress(Phase.PLAYING, period=1, periods=4)
    return p


def service(matches, subs, progress):
    teams = create_autospec(AbstractTeamRepository, instance=True)
    return SubstitutionService(matches, subs, progress, teams)


def error_of(svc, user_id=1):
    with pytest.raises(ApiError) as e:
        svc.get_substitutions(user_id, 5)
    return e.value.status_code, e.value.code


def test_nonexistent_match_is_404(matches, subs, progress):
    matches.get_players.return_value = None
    assert error_of(service(matches, subs, progress)) == (404, None)
    subs.list_by_match.assert_not_called()


def test_user_outside_the_match_is_403_even_if_not_started(matches, subs, progress):
    matches.get_players.return_value = MatchPlayersData(
        id=5, status=MatchStatus.scheduled, league_id=None, user_1_id=1, user_2_id=2
    )
    assert error_of(service(matches, subs, progress), user_id=9) == (403, None)


@pytest.mark.parametrize(
    "status", [MatchStatus.scheduled, MatchStatus.finished, MatchStatus.cancelled]
)
def test_not_started_is_409(matches, subs, progress, status):
    matches.get_players.return_value = MatchPlayersData(
        id=5, status=status, league_id=None, user_1_id=1, user_2_id=2
    )
    assert error_of(service(matches, subs, progress)) == (409, "matchNotStarted")


def test_maps_each_team_and_null_for_the_one_without_substitutions(matches, subs, progress):
    subs.list_by_match.return_value = [
        SubstitutionData(user_id=2, starter_name="A", substitute_name="B")
    ]
    out = service(matches, subs, progress).get_substitutions(1, 5)
    assert out.club1 is None
    assert (out.club2.starter_name, out.club2.substitute_name) == ("A", "B")


def test_same_result_for_both_users(matches, subs, progress):
    subs.list_by_match.return_value = [
        SubstitutionData(user_id=2, starter_name="C2", substitute_name="D2"),
        SubstitutionData(user_id=1, starter_name="C1", substitute_name="D1"),
    ]
    s = service(matches, subs, progress)

    for user_id in (1, 2):
        out = s.get_substitutions(user_id, 5)
        # club1 siempre es user_1 y club2 siempre user_2, sea quien sea el que consulta.
        assert (out.club1.starter_name, out.club1.substitute_name) == ("C1", "D1")
        assert (out.club2.starter_name, out.club2.substitute_name) == ("C2", "D2")
    assert s.get_substitutions(1, 5) == s.get_substitutions(2, 5)


# --- aplicada vs. pendiente ---------------------------------------------------


def test_outside_a_pause_it_returns_the_pending_substitution(matches, subs, progress):
    subs.list_by_match.return_value = [
        SubstitutionData(user_id=1, starter_name="P1", substitute_name="P2")
    ]
    subs.list_applied_by_match.return_value = [
        SubstitutionData(user_id=1, starter_name="A1", substitute_name="A2")
    ]
    out = service(matches, subs, progress).get_substitutions(1, 5)
    assert (out.club1.starter_name, out.club1.substitute_name) == ("P1", "P2")
    subs.list_applied_by_match.assert_not_called()


def test_during_a_pause_it_returns_the_applied_substitution(matches, subs, progress):
    progress.progress.return_value = MatchProgress(Phase.PAUSED, period=1, periods=4)
    subs.list_by_match.return_value = [
        SubstitutionData(user_id=1, starter_name="P1", substitute_name="P2")
    ]
    subs.list_applied_by_match.return_value = [
        SubstitutionData(user_id=2, starter_name="A1", substitute_name="A2")
    ]
    out = service(matches, subs, progress).get_substitutions(1, 5)
    assert out.club1 is None  # el cambio pendiente (PUT durante la pausa) no se ve todavía
    assert (out.club2.starter_name, out.club2.substitute_name) == ("A1", "A2")
    subs.list_by_match.assert_not_called()


def test_during_the_last_pause_it_is_200_with_the_applied_one(matches, subs, progress):
    progress.progress.return_value = MatchProgress(Phase.PAUSED, period=3, periods=4)
    out = service(matches, subs, progress).get_substitutions(1, 5)
    assert out.club1 is None and out.club2 is None


@pytest.mark.parametrize("phase", [Phase.COUNTDOWN, Phase.PLAYING])
def test_after_the_last_pause_there_are_no_pauses_left(matches, subs, progress, phase):
    progress.progress.return_value = MatchProgress(phase, period=4, periods=4)
    assert error_of(service(matches, subs, progress)) == (409, "noPausesLeft")
    subs.list_by_match.assert_not_called()


@pytest.mark.parametrize("period", [1, 2, 3])
def test_before_the_last_period_it_is_not_no_pauses_left(matches, subs, progress, period):
    progress.progress.return_value = MatchProgress(Phase.PLAYING, period=period, periods=4)
    assert service(matches, subs, progress).get_substitutions(1, 5).club1 is None


def test_a_match_with_a_single_period_has_no_pauses(matches, subs, progress):
    progress.progress.return_value = MatchProgress(Phase.PLAYING, period=1, periods=1)
    assert error_of(service(matches, subs, progress)) == (409, "noPausesLeft")


def test_in_penalties_is_409_and_goes_before_no_pauses_left(matches, subs, progress):
    progress.progress.return_value = MatchProgress(Phase.PENALTIES, period=4, periods=4)
    assert error_of(service(matches, subs, progress)) == (409, "matchInPenalties")


def test_not_started_goes_before_the_phase_errors(matches, subs, progress):
    matches.get_players.return_value = MatchPlayersData(
        id=5, status=MatchStatus.finished, league_id=None, user_1_id=1, user_2_id=2
    )
    progress.progress.return_value = MatchProgress(Phase.PLAYING, period=4, periods=4)
    assert error_of(service(matches, subs, progress)) == (409, "matchNotStarted")


def test_without_progress_it_answers_the_pending_one(matches, subs, progress):
    # El partido no se juega en este proceso: no se conoce la fase.
    progress.progress.return_value = None
    subs.list_by_match.return_value = [
        SubstitutionData(user_id=1, starter_name="P1", substitute_name="P2")
    ]
    out = service(matches, subs, progress).get_substitutions(1, 5)
    assert out.club1.starter_name == "P1"
