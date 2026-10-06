import pytest
from app.models.player import Player


@pytest.fixture()
def create_player(db_session):
    def _create(user, name="Jugador Test") -> Player:
        player = Player(
            user_id=user.id,
            name=name,
            power=60,
            agility=60,
            control=60,
            strength=60,
            speed=60,
        )
        db_session.add(player)
        db_session.commit()
        return player

    return _create


def test_get_my_players_requires_auth(client):
    resp = client.get("/players/me")
    assert resp.status_code == 401


def test_get_my_players_empty_list(make_user, auth_cookies, client):
    user = make_user(1)
    cookies = auth_cookies(user.id)

    client.cookies.update(cookies)

    resp = client.get("/players/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pageSize"] == 50


def test_get_my_players_returns_only_owned_players(make_user, create_player, auth_cookies, client):
    user1 = make_user(1)
    user2 = make_user(2)

    create_player(user1, "Jugador 1")
    create_player(user1, "Jugador 2")
    create_player(user2, "Jugador Ajeno")

    cookies = auth_cookies(user1.id)
    client.cookies.update(cookies)

    resp = client.get("/players/me")
    assert resp.status_code == 200

    data = resp.json()["items"]
    assert len(data) == 2
    names = [p["name"] for p in data]
    assert "Jugador 1" in names
    assert "Jugador 2" in names
    assert "Jugador Ajeno" not in names


def test_get_my_players_response_structure(make_user, create_player, auth_cookies, client):
    user = make_user(1)
    create_player(user, "Estructura Test")

    client.cookies.update(auth_cookies(user.id))
    resp = client.get("/players/me")

    assert resp.status_code == 200
    data = resp.json()

    # Validar Paginación
    assert "items" in data
    assert data["page"] == 1
    assert data["pageSize"] == 50
    assert data["total"] == 1

    # Validar Estructura del Jugador
    item = data["items"][0]
    assert item["name"] == "Estructura Test"
    assert item["deletable"] is True
    assert "stats" in item
    assert item["stats"]["power"] == 60
    assert item["stats"]["speed"] == 60


@pytest.mark.parametrize("bad_page", ["abc", "-1", "99999999999"])
def test_get_my_players_bad_pagination_returns_400(make_user, auth_cookies, client, bad_page):
    user = make_user(1)
    client.cookies.update(auth_cookies(user.id))

    resp = client.get(f"/players/me?page={bad_page}")

    assert resp.status_code == 400


def test_get_my_players_filtering_and_escaping_db(make_user, create_player, auth_cookies, client):
    user = make_user(1)
    create_player(user, "Lionel Messi")
    create_player(user, "100% Argentino")
    create_player(user, "El_Fideo")

    client.cookies.update(auth_cookies(user.id))

    # 1. Búsqueda normal case-insensitive
    resp = client.get("/players/me?name=messi")
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Lionel Messi"

    # 2. Búsqueda escapando el comodín de SQL "%"
    resp = client.get("/players/me?name=100%")
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "100% Argentino"

    # 3. Búsqueda escapando el comodín de SQL "_"
    resp = client.get("/players/me?name=El_")
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "El_Fideo"


def test_get_my_players_empty_name_parameter_is_ignored(
    make_user, create_player, auth_cookies, client
):
    user = make_user(1)
    create_player(user, "Jugador 1")
    create_player(user, "Jugador 2")

    client.cookies.update(auth_cookies(user.id))

    # ?name= vacío debería traer a todos
    resp = client.get("/players/me?name=")
    assert resp.json()["total"] == 2
