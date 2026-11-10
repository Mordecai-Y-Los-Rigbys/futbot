import pytest

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.services.league_fixture_channel import (
    LeagueFixtureState,
    build_fixture_payload,
    reject_unless_started,
)
from app.tests.unit.league_fixture_fakes import match


def state(status=LeagueStatus.started, matches=None):
    return LeagueFixtureState(
        league_id=5,
        status=status,
        matches=[match(1, 7, 8)] if matches is None else matches,
    )


def test_started_is_admitted():
    assert reject_unless_started(LeagueStatus.started) is None


@pytest.mark.parametrize(
    "status, reason",
    [
        (LeagueStatus.preparation, "leagueNotStarted"),
        (LeagueStatus.finished, "leagueFinished"),
        (LeagueStatus.cancelled, "leagueCancelled"),
    ],
)
def test_other_states_are_rejected_with_409(status, reason):
    error = reject_unless_started(status)
    assert (error.status_code, error.code) == (409, reason)


def test_payload_matches_the_contract():
    finished = match(1, 7, 8, status=MatchStatus.finished, score=(2, 1))
    assert build_fixture_payload(state(matches=[finished])) == {
        "type": "leagueFixture",
        "leagueStatus": "started",
        "fixture": [
            {
                "id": 1,
                "leagueId": 5,
                "name": None,
                "status": "finished",
                "club1": {"id": 7, "username": "user7", "name": "club7", "avatar": 1},
                "club2": {"id": 8, "username": "user8", "name": "club8", "avatar": 1},
                "scheduledAt": "2026-01-01T18:00:00Z",
                "createdAt": "2025-12-31T18:00:00Z",
                "result": {"score1": 2, "score2": 1, "penalties": None},
            }
        ],
    }


def test_unfinished_match_has_no_result():
    assert build_fixture_payload(state())["fixture"][0]["result"] is None


def test_the_repository_order_is_kept():
    matches = [match(3, 7, 8, hours=0), match(1, 7, 9, hours=1), match(2, 8, 9, hours=2)]
    payload = build_fixture_payload(state(matches=matches))
    assert [m["id"] for m in payload["fixture"]] == [3, 1, 2]


def test_cancelled_league_has_an_empty_fixture():
    payload = build_fixture_payload(state(status=LeagueStatus.cancelled))
    assert (payload["leagueStatus"], payload["fixture"]) == ("cancelled", [])


def test_finished_league_keeps_its_fixture():
    payload = build_fixture_payload(state(status=LeagueStatus.finished))
    assert (payload["leagueStatus"], len(payload["fixture"])) == ("finished", 1)