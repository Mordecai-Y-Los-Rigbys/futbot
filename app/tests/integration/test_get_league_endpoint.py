import pytest

from app.models.league_participant import LeagueParticipant

DETAIL_FIELDS = {
    "id",
    "name",
    "creator",
    "status",
    "participantsCount",
    "maxParticipants",
    "minParticipants",
    "private",
    "allowDraws",
    "createdAt",
    "joined",
}


@pytest.fixture()
def owner(create_user):
    return create_user("mgonzalez", "Boca Juniors FC")


def leave(db_session, league, user):
    """No hay endpoint para abandonar: se borra la inscripción directo."""
    db_session.query(LeagueParticipant).filter_by(league_id=league.id, user_id=user.id).delete()
    db_session.commit()


# --- 401 / 404 ----------------------------------------------------------------


@pytest.mark.parametrize("league_id", ["1", "abc", "0", "2147483648", "99999"])
def test_without_session_returns_401_for_any_id(client, owner, make_league, league_id):
    make_league(owner)
    response = client.get(f"/leagues/{league_id}")
    assert response.status_code == 401
    assert response.json()["code"] is None


@pytest.mark.parametrize("league_id", ["abc", "0", "-1", "1.5", "2147483648", "99999"])
def test_invalid_or_missing_id_returns_404(login_as, owner, make_league, league_id):
    make_league(owner)
    response = login_as(owner).get(f"/leagues/{league_id}")
    assert response.status_code == 404
    assert response.json()["code"] is None


# --- 200 ----------------------------------------------------------------------


def test_returns_the_full_detail(login_as, owner, make_league):
    league = make_league(owner, "Liga Argentina", max_participants=10)

    response = login_as(owner).get(f"/leagues/{league.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == league.id
    assert body["name"] == "Liga Argentina"
    assert body["status"] == "preparation"
    assert body["maxParticipants"] == 10
    assert body["minParticipants"] == 3
    assert body["private"] is False
    assert body["allowDraws"] is True
    assert body["createdAt"].endswith("Z")
    assert body["creator"] == {
        "id": owner.id,
        "username": "mgonzalez",
        "name": "Boca Juniors FC",
        "avatar": owner.avatar,
    }


@pytest.mark.parametrize("status", ["preparation", "started", "cancelled", "finished"])
def test_leagues_in_any_status_can_be_read(login_as, owner, make_league, status):
    league = make_league(owner, status=status)
    response = login_as(owner).get(f"/leagues/{league.id}")
    assert response.status_code == 200
    assert response.json()["status"] == status


def test_each_league_returns_its_own_data(login_as, owner, create_user, make_league):
    other = create_user("otro", "Racing Club")
    first = make_league(owner, "Primera")
    second = make_league(other, "Segunda")
    api = login_as(owner)

    assert api.get(f"/leagues/{first.id}").json()["name"] == "Primera"
    detail = api.get(f"/leagues/{second.id}").json()
    assert detail["name"] == "Segunda"
    assert detail["creator"]["username"] == "otro"


# --- participantsCount --------------------------------------------------------


def test_participants_count_includes_the_creator(login_as, owner, make_league):
    league = make_league(owner)
    assert login_as(owner).get(f"/leagues/{league.id}").json()["participantsCount"] == 1


def test_participants_count_changes_when_someone_joins_or_leaves(
    login_as, owner, create_user, make_league, add_participant, db_session
):
    league = make_league(owner)
    guest = create_user("invitado")
    api = login_as(owner)

    add_participant(league, guest)
    assert api.get(f"/leagues/{league.id}").json()["participantsCount"] == 2

    leave(db_session, league, guest)
    assert api.get(f"/leagues/{league.id}").json()["participantsCount"] == 1


def test_participants_count_is_per_league(
    login_as, owner, create_user, make_league, add_participant
):
    crowded = make_league(owner, "Llena")
    empty = make_league(owner, "Vacía")
    for name in ("a", "b", "c"):
        add_participant(crowded, create_user(name))
    api = login_as(owner)

    assert api.get(f"/leagues/{crowded.id}").json()["participantsCount"] == 4
    assert api.get(f"/leagues/{empty.id}").json()["participantsCount"] == 1


# --- joined -------------------------------------------------------------------


def test_joined_is_true_for_the_creator(login_as, owner, make_league):
    league = make_league(owner)
    assert login_as(owner).get(f"/leagues/{league.id}").json()["joined"] is True


def test_joined_is_true_for_a_participant_and_false_for_the_rest(
    login_as, owner, create_user, make_league, add_participant
):
    league = make_league(owner)
    participant = create_user("participante")
    stranger = create_user("extraño")
    add_participant(league, participant)

    assert login_as(participant).get(f"/leagues/{league.id}").json()["joined"] is True
    assert login_as(stranger).get(f"/leagues/{league.id}").json()["joined"] is False


def test_joined_follows_joining_and_leaving(
    login_as, owner, create_user, make_league, add_participant, db_session
):
    league = make_league(owner)
    guest = create_user("invitado")
    api = login_as(guest)

    assert api.get(f"/leagues/{league.id}").json()["joined"] is False
    add_participant(league, guest)
    assert api.get(f"/leagues/{league.id}").json()["joined"] is True
    leave(db_session, league, guest)
    assert api.get(f"/leagues/{league.id}").json()["joined"] is False


def test_joined_depends_only_on_the_logged_user(
    login_as, owner, create_user, make_league, add_participant
):
    """Que otro usuario participe no hace que `joined` sea true para mí."""
    league = make_league(owner)
    stranger = create_user("extraño")
    add_participant(league, create_user("otro"))

    assert login_as(stranger).get(f"/leagues/{league.id}").json()["joined"] is False


# --- ligas privadas y contraseña ----------------------------------------------


def test_private_league_is_readable_by_a_non_participant(
    login_as, owner, create_user, make_league
):
    league = make_league(owner, private=True)
    stranger = create_user("extraño")

    response = login_as(stranger).get(f"/leagues/{league.id}")

    assert response.status_code == 200
    assert response.json()["private"] is True
    assert response.json()["joined"] is False


def test_the_password_is_never_exposed(login_as, owner, create_user, make_league):
    """make_league guarda 'secret' como contraseña de las ligas privadas."""
    league = make_league(owner, private=True)
    stranger = create_user("extraño")

    for user in (owner, stranger):
        response = login_as(user).get(f"/leagues/{league.id}")
        body = response.json()
        assert "password" not in body
        assert "password" not in body["creator"]
        assert "secret" not in response.text


def test_endpoint_is_read_only(login_as, owner, make_league, db_session):
    league = make_league(owner)
    api = login_as(owner)

    api.get(f"/leagues/{league.id}")
    api.get(f"/leagues/{league.id}")

    assert db_session.query(LeagueParticipant).filter_by(league_id=league.id).count() == 1
