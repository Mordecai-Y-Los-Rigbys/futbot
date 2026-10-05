import pytest

from app.models.behavior import Behavior
from app.models.user import User
from app.repositories.user_sqlalchemy import SqlAlchemyUserRepository
from app.services.session_service import SessionService
from app.services.behavior_service import BehaviorService
from app.simulation.behaviors.default_behaviors import DEFAULT_BEHAVIORS

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
    def fail_to_create_default_behaviors(self, user_id):
        raise RuntimeError("falló la creación de behaviors")

    monkeypatch.setattr(BehaviorService, "create_default_behaviors", fail_to_create_default_behaviors)

    with pytest.raises(RuntimeError):
        register(client)

    assert db_session.query(User).count() == 0
    assert db_session.query(Behavior).count() == 0

    monkeypatch.undo()
    assert register(client).status_code == 201  # el email quedó libre

def test_if_the_session_fails_nothing_is_saved(client, db_session, monkeypatch):
    # Si falla, el usuario y sus behaviors no tienen que quedar guardados.
    def fail_to_create_session(self, user_id):
        raise RuntimeError("falló la creación de la sesión")

    monkeypatch.setattr(SessionService, "create", fail_to_create_session)

    with pytest.raises(RuntimeError):
        register(client)

    assert db_session.query(User).count() == 0
    assert db_session.query(Behavior).count() == 0

def test_duplicate_email_leaves_no_orphan_behaviors(client, db_session):
    assert register(client, "dup@test.com", "a").status_code == 201

    response = register(client, "dup@test.com", "b")

    assert response.status_code == 409
    assert db_session.query(User).count() == 1
    assert db_session.query(Behavior).count() == len(DEFAULT_BEHAVIORS)

def test_duplicate_email_detected_by_the_database_leaves_nothing(
    client, db_session, monkeypatch
):
    # Simula dos registros simultáneos con el mismo email: los dos pasan el
    # chequeo previo y el duplicado recién lo detecta el INSERT (savepoint).
    assert register(client, "dup@test.com", "a").status_code == 201

    def never_finds_a_user(self, email):
        return None

    # Simula que el chequeo no ve al otro usuario
    monkeypatch.setattr(SqlAlchemyUserRepository, "get_by_email", never_finds_a_user)

    # Entonces acá el registro ve que no hay duplicado y va a crear el usuario,
    # pero el INSERT falla
    response = register(client, "dup@test.com", "b")

    assert response.status_code == 409
    assert db_session.query(User).count() == 1
    assert db_session.query(Behavior).count() == len(DEFAULT_BEHAVIORS)
