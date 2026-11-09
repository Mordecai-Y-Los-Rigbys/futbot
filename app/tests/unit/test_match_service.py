from datetime import datetime, timezone
from unittest.mock import create_autospec

import pytest

from app.domain.match import MatchStatus
from app.domain.team_member import MemberRole
from app.errors import ApiError
from app.repositories.friendly_abstract import FriendlyClubData
from app.repositories.league_access_abstract import LeagueAccessInfo
from app.repositories.match_abstract import (
    AbstractMatchRepository,
    MatchDetailData,
    PenaltyShootoutData,
)
from app.repositories.team_abstract import AbstractTeamRepository, LineupPlayerData
from app.services.league_access_service import LeagueAccessService
from app.services.match_service import MatchService

CREATED = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
SCHEDULED = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
PRIVATE = LeagueAccessInfo(9, 1, True, "secret")  # creada por el usuario 1
PUBLIC = LeagueAccessInfo(9, 1, False, None)
OUTSIDER = 7


def club(user_id: int, avatar: int = 1) -> FriendlyClubData:
    return FriendlyClubData(
        id=user_id,
        username=f"user{user_id}",
        club_name=f"club{user_id}",
        avatar=avatar,
    )


def detail(
    *,
    league: LeagueAccessInfo | None = None,
    club2: FriendlyClubData | None = club(2),
    status: MatchStatus = MatchStatus.scheduled,
    score_1: int | None = None,
    score_2: int | None = None,
) -> MatchDetailData:
    """Partido entre los usuarios 1 y 2. Amistoso a menos que se pase 'league'."""
    return MatchDetailData(
        id=5,
        league_id=league.id if league else None,
        name=None if league else "Amistoso",
        status=status,
        club1=club(1),
        club2=club2,
        scheduled_at=SCHEDULED if league else None,
        created_at=CREATED,
        score_1=score_1,
        score_2=score_2,
        league=league,
    )


@pytest.fixture()
def matches():
    m = create_autospec(AbstractMatchRepository, instance=True)
    m.get_detail.return_value = detail()
    return m


@pytest.fixture()
def access():
    return create_autospec(LeagueAccessService, instance=True)


@pytest.fixture()
def teams():
    repo = create_autospec(AbstractTeamRepository, instance=True)
    repo.get_lineup.return_value = []
    return repo


@pytest.fixture()
def service(matches, access, teams):
    return MatchService(matches, access, teams)


def get_match(service, user_id):
    return service.get_match(5, "sid", user_id)


def get_lineups(service, user_id):
    return service.get_lineups(5, "sid", user_id)


# Las reglas de acceso son las mismas en los dos métodos (pasan por _get_visible).
BOTH_METHODS = pytest.mark.parametrize(
    "call", [get_match, get_lineups], ids=["get_match", "get_lineups"]
)


def error_of(call, service, user_id=OUTSIDER):
    with pytest.raises(ApiError) as error:
        call(service, user_id)
    return error.value.status_code, error.value.code


@BOTH_METHODS
def test_nonexistent_match_is_404(call, service, matches, access, teams):
    matches.get_detail.return_value = None
    assert error_of(call, service) == (404, None)
    access.require_access.assert_not_called()
    teams.get_lineup.assert_not_called()


@BOTH_METHODS
@pytest.mark.parametrize("league", [None, PRIVATE], ids=["amistoso", "liga privada"])
@pytest.mark.parametrize("user_id", [1, 2])
def test_players_see_their_match(call, service, matches, access, league, user_id):
    matches.get_detail.return_value = detail(league=league)
    call(service, user_id)
    access.require_access.assert_not_called()


@BOTH_METHODS
@pytest.mark.parametrize("club2", [club(2), None], ids=["con rival", "sin rival"])
def test_friendly_outsider_is_403_not_a_player(call, service, matches, access, teams, club2):
    matches.get_detail.return_value = detail(club2=club2)
    assert error_of(call, service) == (403, "notAPlayerInMatch")
    access.require_access.assert_not_called()
    teams.get_lineup.assert_not_called()


@BOTH_METHODS
@pytest.mark.parametrize("league", [PUBLIC, PRIVATE], ids=["pública", "privada"])
def test_league_spectator_with_access_sees_it(call, service, matches, access, league):
    matches.get_detail.return_value = detail(league=league)
    call(service, OUTSIDER)
    access.require_access.assert_called_once_with("sid", OUTSIDER, league)


@BOTH_METHODS
def test_private_league_without_access_is_403(call, service, matches, access, teams):
    matches.get_detail.return_value = detail(league=PRIVATE)
    access.require_access.side_effect = ApiError(403, "leagueAccessRequired", "x")
    assert error_of(call, service) == (403, "leagueAccessRequired")
    teams.get_lineup.assert_not_called()


@pytest.mark.parametrize(
    "status", [MatchStatus.scheduled, MatchStatus.started, MatchStatus.cancelled]
)
def test_result_is_null_unless_finished(service, matches, status):
    matches.get_detail.return_value = detail(status=status)
    assert service.get_match(5, "sid", 1).result is None


def test_finished_match_without_shootout_has_scores_and_null_penalties(service, matches):
    matches.get_detail.return_value = detail(status=MatchStatus.finished, score_1=2, score_2=1)
    assert service.get_match(5, "sid", 1).result == {
        "score1": 2,
        "score2": 1,
        "penalties": None,
    }


KICKS = [
    {"club": "club1", "kickerId": 3, "kickerName": "J3", "round": 1, "scored": True},
    {"club": "club2", "kickerId": 13, "kickerName": "J13", "round": 1, "scored": False},
]


@pytest.mark.parametrize("winner, club", [(1, "club1"), (2, "club2")])
def test_finished_match_with_shootout_has_the_penalties(service, matches, winner, club):
    shootout = PenaltyShootoutData(score_1=1, score_2=1, winner=winner, kicks=KICKS)
    finished = detail(league=PUBLIC, status=MatchStatus.finished, score_1=0, score_2=0)
    matches.get_detail.return_value = finished.model_copy(update={"penalties": shootout})

    assert service.get_match(5, "sid", 1).result == {
        "score1": 0,
        "score2": 0,
        "penalties": {"score1": 1, "score2": 1, "winner": club, "kicks": KICKS},
    }


def test_maps_clubs_with_avatar_and_league_fields(service, matches):
    matches.get_detail.return_value = detail(league=PRIVATE).model_copy(
        update={
            "club1": club(1, avatar=2),
            "club2": club(2, avatar=4),
        }
    )
    out = service.get_match(5, "sid", 1)
    assert out.club1.model_dump() == {"id": 1, "username": "user1", "name": "club1", "avatar": 2}
    assert out.club2.model_dump() == {"id": 2, "username": "user2", "name": "club2", "avatar": 4}
    assert (out.league_id, out.name, out.status) == (9, None, "scheduled")
    assert out.scheduled_at == SCHEDULED and out.created_at == CREATED


# --- GET /matches/{id}/lineups -------------------------------------------------


def starters(user_id: int) -> list[LineupPlayerData]:
    """Titulares del usuario, a propósito fuera del orden del contrato."""
    base = user_id * 10
    return [
        LineupPlayerData(player_id=base + 1, name=f"def{user_id}", role=MemberRole.defense),
        LineupPlayerData(player_id=base + 3, name=f"del{user_id}", role=MemberRole.forward),
        LineupPlayerData(player_id=base + 2, name=f"med{user_id}", role=MemberRole.midfield),
    ]


def lineup_of(user_id: int) -> list[dict]:
    """Lo que tiene que devolver el service: delantero, mediocampista y defensor."""
    base = user_id * 10
    return [
        {"player_id": base + 3, "name": f"del{user_id}", "role": "forward"},
        {"player_id": base + 2, "name": f"med{user_id}", "role": "midfield"},
        {"player_id": base + 1, "name": f"def{user_id}", "role": "defense"},
    ]


@pytest.mark.parametrize("league", [None, PRIVATE], ids=["amistoso", "liga"])
def test_lineups_have_both_clubs_in_contract_order(service, matches, teams, league):
    matches.get_detail.return_value = detail(league=league)
    teams.get_lineup.side_effect = lambda match_id, league_id, user_id: starters(user_id)

    lineups = service.get_lineups(5, "sid", 1).model_dump()

    assert lineups == {"club1": lineup_of(1), "club2": lineup_of(2)}
    league_id = league.id if league else None
    called_with = {call.args for call in teams.get_lineup.call_args_list}
    assert called_with == {(5, league_id, 1), (5, league_id, 2)}


def test_lineups_of_a_waiting_friendly_have_no_second_club(service, matches, teams):
    matches.get_detail.return_value = detail(club2=None)
    teams.get_lineup.return_value = starters(1)

    lineups = service.get_lineups(5, "sid", 1)

    assert lineups.club2 is None
    teams.get_lineup.assert_called_once_with(5, None, 1)


@pytest.mark.parametrize("status", list(MatchStatus))
def test_lineups_do_not_depend_on_match_status(service, matches, teams, status):
    matches.get_detail.return_value = detail(status=status)
    teams.get_lineup.side_effect = lambda match_id, league_id, user_id: starters(user_id)

    lineups = service.get_lineups(5, "sid", 1).model_dump()

    assert lineups == {"club1": lineup_of(1), "club2": lineup_of(2)}
