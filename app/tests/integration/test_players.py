from app.models.player import Player


def valid_payload():
    return {
        "name": "Lionel",
        "power": 60,
        "agility": 60,
        "control": 60,
        "strength": 60,
        "speed": 60,
    }


def test_create_player_success(client, auth_cookies):
    client.cookies = auth_cookies(1)
    response = client.post("/players", json=valid_payload())

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["name"] == "Lionel"
    assert data["deletable"] is True

    assert "stats" in data
    stats = data["stats"]
    assert stats["power"] == 60
    assert stats["speed"] == 60


def test_create_player_unauthorized(client):
    response = client.post("/players", json=valid_payload())
    assert response.status_code == 401


def test_create_player_validation_error_format(client, auth_cookies):
    payload = valid_payload()
    payload["power"] = 90  # Sumará 330

    client.cookies = auth_cookies(1)
    response = client.post("/players", json=payload)

    assert response.status_code == 400
    data = response.json()

    assert data["code"] == "invalidFields"
    assert data["errors"] == [{"field": "stats", "reason": "invalidSum"}]
    assert data["message"]


def test_create_player_malformed_json(client, auth_cookies):
    client.cookies = auth_cookies(1)

    response = client.post(
        "/players", content=b"esto no es un json {,,}", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert response.json()["errors"] == [
        {"field": f, "reason": "required"}
        for f in ("name", "power", "agility", "control", "strength", "speed")
    ]


def test_create_player_is_persisted(client, auth_cookies, db_session):
    client.cookies = auth_cookies(1)
    response = client.post("/players", json=valid_payload())
    assert response.status_code == 201

    db_session.rollback()
    assert db_session.get(Player, response.json()["id"]) is not None


def test_create_player_reports_every_invalid_field_and_persists_nothing(
    client, auth_cookies, db_session
):
    client.cookies = auth_cookies(1)
    payload = valid_payload()
    payload.update(name="x" * 21, power="60", control=10)
    del payload["speed"]

    response = client.post("/players", json=payload)

    assert response.status_code == 400
    assert response.json()["errors"] == [
        {"field": "name", "reason": "tooLong"},
        {"field": "power", "reason": "invalidType"},
        {"field": "control", "reason": "outOfRange"},
        {"field": "speed", "reason": "required"},
    ]
    db_session.rollback()
    assert db_session.query(Player).count() == 0
