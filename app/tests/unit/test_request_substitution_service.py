from unittest.mock import create_autospec

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
    teams.get_team_player_ids.side_effect = lambda _mid, _league, _uid, *, substitutes: (
        {13, 14, 15} if substitutes else {10, 11, 12}
    )
    teams.get_member_id.side_effect = lambda mid, league, uid, pid: pid + 100
    substitutions = create_autospec(AbstractSubstitutionRepository, instance=True)
    progress = create_autospec(MatchProgressReader, instance=True)
    progress.progress.return_value = MatchProgress(Phase.PLAYING, period=2, periods=4)
    return matches, teams, substitutions, progress


def test_valid_request_persists_member_ids(setup):
    matches, teams, repo, progress = setup
    service = SubstitutionService(matches, repo, progress, teams)

    service.request_substitution(7, 5, {"starterId": 10, "substituteId": 13})

    repo.upsert.assert_called_once_with(5, 7, 113, 110)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({}, [("starterId", "required"), ("substituteId", "required")]),
        ({"starterId": "10", "substituteId": 13}, [("starterId", "invalidType")]),
        ({"starterId": 0, "substituteId": 13}, [("starterId", "outOfRange")]),
        ({"starterId": 10, "substituteId": None}, [("substituteId", "invalidType")]),
        ({"starterId": 10, "substituteId": 2**31}, [("substituteId", "outOfRange")]),
    ],
)
def test_field_validation(setup, body, expected):
    matches, teams, repo, progress = setup
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(7, 5, body)
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == expected


def test_both_team_membership_errors_are_reported(setup):
    matches, teams, repo, progress = setup
    teams.get_team_player_ids.side_effect = lambda _mid, _league, _uid, *, substitutes: (
        {14} if substitutes else {11}
    )
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [
        ("starterId", "notStarter"),
        ("substituteId", "notSubstitute"),
    ]


def test_non_player_with_valid_body_is_forbidden(setup):
    matches, teams, repo, progress = setup
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(
            9, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (403, None)
    teams.get_team_player_ids.assert_not_called()


@pytest.mark.parametrize(
    ("match_progress", "code"),
    [
        (MatchProgress(Phase.PENALTIES, period=4, periods=4), "matchInPenalties"),
        (MatchProgress(Phase.PLAYING, period=4, periods=4), "noPausesLeft"),
        (None, "noPausesLeft"),
    ],
)
def test_progress_conflicts(setup, match_progress, code):
    matches, teams, repo, progress = setup
    progress.progress.return_value = match_progress
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (409, code)
    repo.upsert.assert_not_called()


def test_match_not_started_has_precedence_over_progress_conflicts(setup):
    matches, teams, repo, progress = setup
    matches.get_players.return_value.status = MatchStatus.finished
    progress.progress.return_value = MatchProgress(Phase.PENALTIES, period=4, periods=4)
    with pytest.raises(ApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(
            7, 5, {"starterId": 10, "substituteId": 13}
        )
    assert (exc.value.status_code, exc.value.code) == (409, "matchNotStarted")


def test_valid_substitute_field_is_still_checked_when_starter_has_wrong_type(setup):
    matches, teams, repo, progress = setup
    teams.get_team_player_ids.side_effect = [{13, 14, 15}]
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(
            7, 5, {"starterId": "10", "substituteId": 999}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [
        ("starterId", "invalidType"),
        ("substituteId", "notSubstitute"),
    ]


def test_non_player_with_invalid_body_gets_only_field_errors(setup):
    matches, teams, repo, progress = setup
    with pytest.raises(ValidationApiError) as exc:
        SubstitutionService(matches, repo, progress, teams).request_substitution(
            9, 5, {"starterId": "10", "substituteId": 13}
        )
    assert [(e["field"], e["reason"]) for e in exc.value.errors] == [("starterId", "invalidType")]
    teams.get_team_player_ids.assert_not_called()
