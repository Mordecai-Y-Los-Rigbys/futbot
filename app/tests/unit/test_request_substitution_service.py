from types import SimpleNamespace
from unittest.mock import create_autospec
from sqlalchemy.exc import IntegrityError

import pytest

from app.domain.match import MatchStatus
from app.errors import ApiError, ValidationApiError
from app.repositories.match_abstract import AbstractMatchRepository, MatchPlayersData
from app.repositories.substitution_abstract import AbstractSubstitutionRepository
from app.repositories.team_abstract import AbstractTeamRepository
from app.services.match_progress import MatchProgress, MatchProgressReader
from app.services.substitution_service import SubstitutionService
from app.simulation.match_rules import Phase


@pytest.fixture
def setup():
    matches = create_autospec(AbstractMatchRepository, instance=True)
    matches.get_players.return_value = MatchPlayersData(
        id=5, league_id=None, status=MatchStatus.started, user_1_id=7, user_2_id=8
    )
    teams = create_autospec(AbstractTeamRepository, instance=True)
    teams.get_team_player_ids.side_effect = (
        lambda _mid, _league, _uid, *, substitutes:
        {13, 14, 15} if substitutes else {10, 11, 12}
    )
    teams.get_member_id.side_effect = lambda mid, league, uid, pid: pid + 100
    substitutions = create_autospec(AbstractSubstitutionRepository, instance=True)
    progress = create_autospec(MatchProgressReader, instance=True)
    progress.progress.return_value = MatchProgress(Phase.PLAYING, period=1, periods=4)
    return matches, teams, substitutions, progress


def test_valid_request_persists_member_ids(setup):
    matches, teams, repo, progress = setup
    service = SubstitutionService(matches, teams, repo, progress)

    service.request_substitution(7, 5, {"starterId": 10, "substituteId": 13})

    repo.upsert.assert_called_once_with(5, 7, 113, 110)


@pytest.mark.parametrize(("body", "expected"), [
    ({}, [("starterId", "required"), ("substituteId", "required")]),
    ({"starterId": "10", "substituteId": 13}, [("starterId", "invalidType")]),
    ({"starterId": 0, "substituteId": 13}, [("starterId", "outOfRange")]),
    ({"starterId": 10, "substituteId": None}, [("substituteId", "invalidType")]),
    ({"starterId": 10, "substituteId": 2**31}, [("substituteId", "outOfRange")]),
])
def test_field_validation(setup, body, expected):
    matches, teams, repo, progress = setup
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(7, 5, body)
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == expected


def test_both_team_membership_errors_are_reported(setup):
    matches, teams, repo, progress = setup
    teams.get_team_player_ids.side_effect = (
        lambda _mid, _league, _uid, *, substitutes: {14} if substitutes else {11}
    )
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [
        ("starterId", "notStarter"), ("substituteId", "notSubstitute")
    ]


def test_non_player_with_valid_body_is_forbidden(setup):
    matches, teams, repo, progress = setup
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            9, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (403, None)
    teams.get_team_player_ids.assert_not_called()


@pytest.mark.parametrize(("state", "code"), [
    (MatchProgress(Phase.PLAYING, period=1, periods=4, in_penalties=True), "matchInPenalties"),
    # último período: ya no empieza ninguna pausa
    (MatchProgress(Phase.PLAYING, period=4, periods=4), "noPausesLeft"),
    # durante la última pausa: no hay una siguiente donde aplicar el cambio
    (MatchProgress(Phase.PAUSED, period=3, periods=4), "noPausesLeft"),
    # el partido no se juega en este proceso: nadie aplicaría el cambio
    (None, "noPausesLeft"),
])
def test_progress_conflicts(setup, state, code):
    matches, teams, repo, progress = setup
    progress.progress.return_value = state
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (409, code)
    repo.upsert.assert_not_called()


def test_put_during_a_pause_that_is_not_the_last_is_accepted(setup):
    matches, teams, repo, progress = setup
    progress.progress.return_value = MatchProgress(Phase.PAUSED, period=2, periods=4)
    SubstitutionService(matches, teams, repo, progress).request_substitution(
        7, 5, {"starterId": 10, "substituteId": 13}
    )
    repo.upsert.assert_called_once_with(5, 7, 113, 110)


def test_match_not_started_has_precedence_over_progress_conflicts(setup):
    matches, teams, repo, progress = setup
    matches.get_players.return_value.status = MatchStatus.finished
    progress.progress.return_value = MatchProgress(
        Phase.PLAYING, period=1, periods=4, in_penalties=True
    )
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (409, "matchNotStarted")


def test_valid_substitute_field_is_still_checked_when_starter_has_wrong_type(setup):
    matches, teams, repo, progress = setup
    teams.get_team_player_ids.side_effect = [{13, 14, 15}]
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": "10", "substituteId": 999}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [
        ("starterId", "invalidType"), ("substituteId", "notSubstitute")
    ]


def test_non_player_with_invalid_body_gets_only_field_errors(setup):
    matches, teams, repo, progress = setup
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            9, 5, {"starterId": "10", "substituteId": 13}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [
        ("starterId", "invalidType")
    ]
    teams.get_team_player_ids.assert_not_called()

def check_violation():
    return IntegrityError("stmt", {}, SimpleNamespace(pgcode="23514"))


def test_trigger_rejection_is_reported_as_field_errors(setup):
    matches, teams, repo, progress = setup
    repo.upsert.side_effect = check_violation()
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [
        ("starterId", "notStarter"), ("substituteId", "notSubstitute")
    ]


def test_trigger_rejection_when_the_match_ended_is_409(setup):
    matches, teams, repo, progress = setup
    repo.upsert.side_effect = check_violation()
    matches.get_players.side_effect = [
        matches.get_players.return_value,
        MatchPlayersData(id=5, league_id=None, status=MatchStatus.finished, user_1_id=7, user_2_id=8),
    ]
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (409, "matchNotStarted")


def test_other_integrity_errors_are_not_swallowed(setup):
    matches, teams, repo, progress = setup
    repo.upsert.side_effect = IntegrityError("stmt", {}, SimpleNamespace(pgcode="23503"))
    with pytest.raises(IntegrityError):
        SubstitutionService(matches, teams, repo, progress).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )