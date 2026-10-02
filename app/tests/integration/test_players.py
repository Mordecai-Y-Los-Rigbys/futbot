import pytest

def valid_payload():
    return {
        "name": "Lionel",
        "power": 60,
        "agility": 60,
        "control": 60,
        "strength": 60,
        "speed": 60
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
    
    assert data["code"] == "invalidStatSum"
    assert "message" in data

def test_create_player_malformed_json(client, auth_cookies):
    client.cookies = auth_cookies(1)
    
    response = client.post(
        "/players", 
        content=b"esto no es un json {,,}", 
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFieldType"