import pytest

from app.domain.behavior import BehaviorType
from app.models.behavior import Behavior
from app.repositories.behavior_abstract import DuplicateBehaviorNameError, UpdateBehaviorData
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository

pytestmark = pytest.mark.integration


def url(behavior_id):
    return f"/behaviors/{behavior_id}"


def add_behavior(db_session, user_id, name, code="x = 1", behavior_type=None):
    behavior = Behavior(
        user_id=user_id,
        name=name,
        code=code,
        type=behavior_type or BehaviorType.player_behavior,
    )
    db_session.add(behavior)
    db_session.commit()
    return behavior


def stored(db_session, behavior):
    db_session.refresh(behavior)
    return (behavior.name, behavior.code, behavior.type)


def test_the_owner_changes_name_and_code_and_keeps_the_type(login, db_session):
    api = login(1)
    coach = add_behavior(db_session, 1, "DT", behavior_type=BehaviorType.coach_behavior)

    response = api.put(
        url(coach.id), json={"name": "DT 2", "code": "x = 2", "type": "playerBehavior"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": coach.id,
        "name": "DT 2",
        "type": "coachBehavior",
        "code": "x = 2",
        "deletable": True,
    }
    assert stored(db_session, coach) == ("DT 2", "x = 2", BehaviorType.coach_behavior)


def test_without_session_is_401(client, db_session, make_user):
    make_user(1)
    behavior = add_behavior(db_session, 1, "mio")

    response = client.put(url(behavior.id), json={"name": "otro", "code": ""})

    assert response.status_code == 401
    assert stored(db_session, behavior)[0] == "mio"


@pytest.mark.parametrize("behavior_id", ["999", "abc"])
def test_a_missing_or_invalid_id_is_404_not_found(login, behavior_id):
    response = login(1).put(url(behavior_id), json={"name": "otro", "code": ""})

    assert response.status_code == 404
    assert response.json()["code"] == "notFound"


def test_another_users_behavior_is_403_and_does_not_change(login, db_session, make_user):
    make_user(2)
    other = add_behavior(db_session, 2, "ajeno")

    response = login(1).put(url(other.id), json={"name": "mio", "code": "x = 2"})

    assert response.status_code == 403
    assert response.json()["code"] is None
    assert stored(db_session, other)[:2] == ("ajeno", "x = 1")


def test_keeping_the_name_is_fine_but_using_another_own_name_is_duplicate(login, db_session):
    api = login(1)
    first = add_behavior(db_session, 1, "primero")
    add_behavior(db_session, 1, "segundo")

    same = api.put(url(first.id), json={"name": "primero", "code": "x = 2"})
    taken = api.put(url(first.id), json={"name": "segundo", "code": "x = 3"})

    assert same.status_code == 200
    assert taken.status_code == 409
    assert (taken.json()["code"], taken.json()["codeError"]) == ("duplicateName", None)
    assert stored(db_session, first)[:2] == ("primero", "x = 2")


def test_an_invalid_code_for_the_stored_type_reports_where(login, db_session):
    api = login(1)
    coach = add_behavior(db_session, 1, "DT", behavior_type=BehaviorType.coach_behavior)

    response = api.put(url(coach.id), json={"name": "DT", "code": "x = 1\nkick()"})

    assert response.status_code == 409
    assert response.json()["codeError"] == {
        "rule": "primitiveNotAllowedForType",
        "line": 2,
        "column": 1,
    }
    assert stored(db_session, coach)[1] == "x = 1"


def test_a_code_too_long_is_409(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "largo")

    response = api.put(url(behavior.id), json={"name": "largo", "code": "x = 1\n" * 251})

    assert response.status_code == 409
    assert response.json()["code"] == "codeTooLong"
    assert stored(db_session, behavior)[1] == "x = 1"


def test_an_unreadable_body_is_400_and_does_not_change(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")

    response = api.put(
        url(behavior.id), content="{roto", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json()["errors"] == [
        {"field": "name", "reason": "required"},
        {"field": "code", "reason": "required"},
    ]
    assert stored(db_session, behavior)[:2] == ("mio", "x = 1")


def test_updating_a_deleted_behavior_returns_none(db_session, make_user):
    make_user(1)
    behavior = add_behavior(db_session, 1, "borrado")
    db_session.delete(behavior)
    db_session.commit()

    result = SqlAlchemyBehaviorRepository(db_session).update(
        behavior.id, UpdateBehaviorData(name="x", code="")
    )

    assert result is None


def test_the_database_rejects_updating_to_a_taken_name(db_session, make_user):
    make_user(1)
    first = add_behavior(db_session, 1, "primero")
    add_behavior(db_session, 1, "segundo")
    repository = SqlAlchemyBehaviorRepository(db_session)

    with pytest.raises(DuplicateBehaviorNameError):
        repository.update(first.id, UpdateBehaviorData(name="segundo", code=""))

    assert stored(db_session, first)[0] == "primero"  # la sesión sigue usable
