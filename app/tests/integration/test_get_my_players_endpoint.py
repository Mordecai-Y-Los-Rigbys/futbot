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
    assert resp.json() == []


def test_get_my_players_returns_only_owned_players(
    make_user, create_player, auth_cookies, client
):
    user1 = make_user(1)
    user2 = make_user(2)

    create_player(user1, "Jugador 1")
    create_player(user1, "Jugador 2")
    create_player(user2, "Jugador Ajeno")

    cookies = auth_cookies(user1.id)

    client.cookies.update(cookies)  
    resp = client.get("/players/me")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = [p["name"] for p in data]
    assert "Jugador 1" in names
    assert "Jugador 2" in names
    assert "Jugador Ajeno" not in names