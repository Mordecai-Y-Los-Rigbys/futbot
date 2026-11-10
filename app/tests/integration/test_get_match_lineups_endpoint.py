"""GET /matches/{id}/lineups contra la base real.

Los equipos salen de `add_team`: los jugadores del usuario N se llaman pN0 a
pN5, y pN0, pN1 y pN2 son delantero, mediocampista y defensor.
"""

import pytest

from app.models.match import Match
from app.models.team_member import MemberRole
from app.tests.integration.match_factories import add_team

pytestmark = pytest.mark.integration


def lineup(user_id: int, teams: dict) -> list[dict]:
    forward, midfield, defense = teams[user_id][:3]
    return [
        {"playerId": forward.player_id, "name": f"p{user_id}0", "role": "forward"},
        {"playerId": midfield.player_id, "name": f"p{user_id}1", "role": "midfield"},
        {"playerId": defense.player_id, "name": f"p{user_id}2", "role": "defense"},
    ]


@pytest.fixture()
def outsider(make_user):
    # Con id fijo, como los usuarios 1 y 2 de `friendly_match` y `league_match`.
    return make_user(7)


@pytest.mark.parametrize("player_id", [1, 2])
def test_friendly_players_get_both_lineups(login_as, friendly_match, player_id):
    match, teams = friendly_match
    response = login_as(match.user_1 if player_id == 1 else match.user_2).get(
        f"/matches/{match.id}/lineups"
    )

    assert response.status_code == 200
    assert response.json() == {"club1": lineup(1, teams), "club2": lineup(2, teams)}


def test_league_match_uses_the_league_teams_and_a_spectator_sees_them(
    login_as, outsider, league_match
):
    match, teams = league_match  # liga pública
    response = login_as(outsider).get(f"/matches/{match.id}/lineups")

    assert response.status_code == 200
    assert response.json() == {"club1": lineup(1, teams), "club2": lineup(2, teams)}


def test_friendly_uses_the_team_of_that_match(login_as, db_session, friendly_match, make_behaviors):
    match, teams = friendly_match
    # Otro amistoso entre los mismos usuarios, con otros jugadores.
    other = Match(user_1_id=1, user_2_id=2)
    db_session.add(other)
    db_session.commit()
    for user_id in (1, 2):
        behavior = make_behaviors(user_id, ["otro"], code="pass")[0]
        add_team(db_session, user_id, behavior, match_id=other.id)

    response = login_as(match.user_1).get(f"/matches/{match.id}/lineups")

    assert response.json() == {"club1": lineup(1, teams), "club2": lineup(2, teams)}


def test_waiting_friendly_has_no_second_club(login_as, db_session, make_user, make_behaviors):
    owner = make_user(1)
    match = Match(user_1_id=1)
    db_session.add(match)
    db_session.commit()
    add_team(db_session, 1, make_behaviors(1, ["b"], code="pass")[0], match_id=match.id)

    response = login_as(owner).get(f"/matches/{match.id}/lineups")

    assert response.status_code == 200
    assert response.json()["club2"] is None
    assert [player["role"] for player in response.json()["club1"]] == [
        "forward",
        "midfield",
        "defense",
    ]


def test_substitution_shows_the_incoming_player_with_the_role_of_the_outgoing_one(
    login_as, db_session, league_match
):
    match, teams = league_match
    forward, substitute = teams[1][0], teams[1][3]
    # Lo que hace una sustitución aplicada: intercambia los roles en el equipo.
    forward.role, substitute.role = MemberRole.substitute, MemberRole.forward
    db_session.commit()

    club1 = login_as(match.user_1).get(f"/matches/{match.id}/lineups").json()["club1"]

    assert club1[0] == {"playerId": substitute.player_id, "name": "p13", "role": "forward"}
    assert forward.player_id not in {player["playerId"] for player in club1}


def test_friendly_outsider_is_403(login_as, outsider, friendly_match):
    match = friendly_match[0]
    response = login_as(outsider).get(f"/matches/{match.id}/lineups")
    assert response.status_code == 403 and response.json()["code"] == "notAPlayerInMatch"


def test_private_league_outsider_is_403_until_unlocking_it(
    login_as, db_session, outsider, league_match
):
    match = league_match[0]
    match.league.private, match.league.password = True, "secret"
    db_session.commit()
    api = login_as(outsider)

    response = api.get(f"/matches/{match.id}/lineups")
    assert response.status_code == 403 and response.json()["code"] == "leagueAccessRequired"

    unlock = api.post(f"/leagues/{match.league_id}/access", json={"password": "secret"})
    assert unlock.status_code == 204
    assert api.get(f"/matches/{match.id}/lineups").status_code == 200


def test_missing_match_is_404_before_403(login_as, outsider):
    response = login_as(outsider).get("/matches/999999/lineups")
    assert response.status_code == 404 and response.json()["code"] is None
