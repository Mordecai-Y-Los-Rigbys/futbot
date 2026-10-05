import pytest

from app.models.behavior import Behavior
from app.models.user import User
from app.services.behavior_service import BehaviorService
from app.services.default_behaviors import DEFAULT_BEHAVIORS

pytestmark = pytest.mark.integration


def register(client, email="nuevo@test.com", username="nuevo"):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "Password123!",
            "clubName": "Club",
            "avatar": 1,
        },
    )


def behaviors_of(db_session, user_id):
    return (
        db_session.query(Behavior)
        .filter(Behavior.user_id == user_id)
        .order_by(Behavior.id)
        .all()
    )


def test_register_creates_the_default_behaviors(client, db_session):
    response = register(client)

    assert response.status_code == 201
    created = behaviors_of(db_session, response.json()["id"])
    assert [(b.name, b.code) for b in created] == [
        (b["name"], b["code"]) for b in DEFAULT_BEHAVIORS
    ]


def test_new_user_sees_them_in_get_behaviors_me(client):
    register(client)  # deja la cookie de sesión en el cliente

    response = client.get("/behaviors/me")

    assert response.status_code == 200
    assert response.json()["total"] == len(DEFAULT_BEHAVIORS)
    assert [b["name"] for b in response.json()["items"]] == [
        b["name"] for b in DEFAULT_BEHAVIORS
    ]


def test_each_user_gets_their_own_copies(client, db_session):
    first = register(client, "a@test.com", "a").json()["id"]
    second = register(client, "b@test.com", "b").json()["id"]

    # Modificar la copia de un usuario no cambia la del otro.
    edited = behaviors_of(db_session, first)[0]
    edited.code = "go_to(0, 0)"
    db_session.commit()

    assert [b.code for b in behaviors_of(db_session, second)] == [
        b["code"] for b in DEFAULT_BEHAVIORS
    ]


def test_if_the_behaviors_fail_nothing_is_saved(client, db_session, monkeypatch):
    def boom(self, user_id):
        raise RuntimeError("falló la creación de behaviors")

    monkeypatch.setattr(BehaviorService, "create_default_behaviors", boom)

    with pytest.raises(RuntimeError):
        register(client)

    assert db_session.query(User).count() == 0
    assert db_session.query(Behavior).count() == 0

    monkeypatch.undo()
    assert register(client).status_code == 201  # el email quedó libre
