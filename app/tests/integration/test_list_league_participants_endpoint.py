import pytest

from app.models.league_participant import LeagueParticipant
from app.models.player import Player

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


@pytest.fixture()
def owner(create_user):
    return create_user("mgonzalez", "Boca Juniors FC")


def participants_url(league):
    return f"/leagues/{league.id}/participants"


def team_of(db_session, make_behaviors, user):
    """Body válido de inscripción: 6 jugadores y behaviors de jugador del usuario."""
    players = [
        Player(
            user_id=user.id, name=f"J{i}", power=60, agility=60, control=60, strength=60, speed=60
        )
        for i in range(6)
    ]
    db_session.add_all(players)
    db_session.commit()
    behaviors = make_behaviors(user.id, [f"b{user.id}-{i}" for i in range(6)])
    return {
        "members": [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ]
    }


# --- 401 / 404 ----------------------------------------------------------------


@pytest.mark.parametrize("league_id", ["1", "abc", "0", "2147483648", "99999"])
def test_without_session_returns_401_for_any_id(client, owner, make_league, league_id):
    make_league(owner)
    client.cookies.clear()

    response = client.get(f"/leagues/{league_id}/participants")

    assert response.status_code == 401
    assert response.json()["code"] is None


def test_invalid_session_returns_401(client, owner, make_league):
    league = make_league(owner)
    client.cookies.set("session_id", "invalid")
    assert client.get(participants_url(league)).status_code == 401


@pytest.mark.parametrize("league_id", ["abc", "0", "-1", "1.5", "2147483648", "99999"])
def test_invalid_or_missing_id_returns_404(login_as, owner, make_league, league_id):
    make_league(owner)

    response = login_as(owner).get(f"/leagues/{league_id}/participants")

    assert response.status_code == 404
    assert response.json()["code"] is None


# --- orden de evaluación ------------------------------------------------------


def test_401_goes_before_404(client):
    client.cookies.clear()
    assert client.get("/leagues/abc/participants").status_code == 401


def test_401_goes_before_403(client, owner, make_league):
    league = make_league(owner, private=True)
    client.cookies.clear()
    assert client.get(participants_url(league)).status_code == 401


def test_404_goes_before_403(login_as, owner, create_user, make_league):
    make_league(owner, private=True)
    stranger = create_user("extraño")
    assert login_as(stranger).get("/leagues/99999/participants").status_code == 404


# --- acceso -------------------------------------------------------------------


def test_public_league_is_readable_by_any_user(login_as, owner, create_user, make_league):
    league = make_league(owner)
    stranger = create_user("extraño")
    assert login_as(stranger).get(participants_url(league)).status_code == 200


def test_private_league_is_readable_by_the_creator_without_unlocking(login_as, owner, make_league):
    league = make_league(owner, private=True)
    assert login_as(owner).get(participants_url(league)).status_code == 200


def test_private_league_is_readable_by_a_participant_without_unlocking(
    login_as, owner, create_user, make_league, add_participant
):
    league = make_league(owner, private=True)
    member = create_user("participante")
    add_participant(league, member)
    assert login_as(member).get(participants_url(league)).status_code == 200


def test_private_league_without_access_returns_403(login_as, owner, create_user, make_league):
    league = make_league(owner, private=True)

    response = login_as(create_user("extraño")).get(participants_url(league))

    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"


def test_unlock_is_per_session(login_as, owner, create_user, make_league):
    league = make_league(owner, private=True)
    stranger = create_user("extraño")
    unlocked_session, other_session = login_as(stranger), login_as(stranger)

    response = unlocked_session.post(f"/leagues/{league.id}/access", json={"password": "secret"})
    assert response.status_code == 204

    assert unlocked_session.get(participants_url(league)).status_code == 200
    response = other_session.get(participants_url(league))
    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"


def test_unlock_is_per_league(login_as, owner, create_user, make_league):
    unlocked_league = make_league(owner, "Una", private=True)
    other_league = make_league(owner, "Otra", private=True)
    api = login_as(create_user("extraño"))

    api.post(f"/leagues/{unlocked_league.id}/access", json={"password": "secret"})

    assert api.get(participants_url(unlocked_league)).status_code == 200
    assert api.get(participants_url(other_league)).status_code == 403


def test_leaving_keeps_access_if_the_session_unlocked_it_with_access(
    login_as, owner, create_user, make_league, add_participant
):
    league = make_league(owner, private=True)
    member = create_user("participante")
    add_participant(league, member)
    api = login_as(member)

    assert api.post(f"/leagues/{league.id}/access").status_code == 204
    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    assert api.get(participants_url(league)).status_code == 200


def test_leaving_keeps_access_if_the_session_unlocked_it_when_joining(
    login_as, owner, create_user, make_league, db_session, make_behaviors
):
    league = make_league(owner, private=True)
    member = create_user("participante")
    api = login_as(member)
    body = {**team_of(db_session, make_behaviors, member), "password": "secret"}

    assert api.post(participants_url(league), json=body).status_code == 201
    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    assert api.get(participants_url(league)).status_code == 200


def test_leaving_from_a_session_that_never_unlocked_loses_access(
    login_as, owner, create_user, make_league, add_participant
):
    league = make_league(owner, private=True)
    member = create_user("participante")
    add_participant(league, member)  # se unió "en otra sesión": ninguna quedó desbloqueada
    api = login_as(member)

    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    response = api.get(participants_url(league))
    assert response.status_code == 403
    assert response.json()["code"] == "leagueAccessRequired"


# --- contenido ----------------------------------------------------------------


def test_returns_only_the_user_club_fields(login_as, owner, make_league):
    league = make_league(owner)

    response = login_as(owner).get(participants_url(league))

    assert response.status_code == 200
    assert response.json() == [
        {"id": owner.id, "username": "mgonzalez", "name": "Boca Juniors FC", "avatar": owner.avatar}
    ]


def test_includes_the_creator_and_is_ordered_by_user_id(
    login_as, create_user, make_league, add_participant
):
    first, second = create_user("primero"), create_user("segundo")
    creator = create_user("creador")  # el id más alto
    league = make_league(creator)
    add_participant(league, second)  # se inscriben en orden distinto al de los ids
    add_participant(league, first)

    body = login_as(creator).get(participants_url(league)).json()

    assert [p["id"] for p in body] == sorted([first.id, second.id, creator.id])
    assert [p["username"] for p in body] == ["primero", "segundo", "creador"]


def test_does_not_include_participants_of_other_leagues(
    login_as, owner, create_user, make_league, add_participant
):
    league = make_league(owner, "Una")
    other = make_league(owner, "Otra")
    add_participant(other, create_user("ajeno"))

    body = login_as(owner).get(participants_url(league)).json()

    assert [p["id"] for p in body] == [owner.id]


def test_reflects_joins_and_leaves(
    login_as, owner, create_user, make_league, add_participant, db_session
):
    league = make_league(owner)
    guest = create_user("invitado")
    api = login_as(owner)

    add_participant(league, guest)
    assert {p["id"] for p in api.get(participants_url(league)).json()} == {owner.id, guest.id}

    db_session.query(LeagueParticipant).filter_by(league_id=league.id, user_id=guest.id).delete()
    db_session.commit()
    assert [p["id"] for p in api.get(participants_url(league)).json()] == [owner.id]


@pytest.mark.parametrize("status", ["preparation", "started", "cancelled", "finished"])
def test_length_matches_participants_count_in_any_status(
    login_as, owner, create_user, make_league, add_participant, status
):
    league = make_league(owner, status=status)
    for name in ("a", "b", "c"):
        add_participant(league, create_user(name))
    api = login_as(owner)

    response = api.get(participants_url(league))

    assert response.status_code == 200
    assert len(response.json()) == 4
    assert len(response.json()) == api.get(f"/leagues/{league.id}").json()["participantsCount"]


def test_the_password_is_never_exposed(login_as, owner, make_league):
    """make_league guarda 'secret' como contraseña de las ligas privadas."""
    league = make_league(owner, private=True)

    response = login_as(owner).get(participants_url(league))

    assert "secret" not in response.text
    assert all("password" not in p for p in response.json())


def test_endpoint_is_read_only(login_as, owner, make_league, db_session):
    league = make_league(owner)
    api = login_as(owner)

    api.get(participants_url(league))
    api.get(participants_url(league))

    assert db_session.query(LeagueParticipant).filter_by(league_id=league.id).count() == 1