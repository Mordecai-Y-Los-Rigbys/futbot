import pytest
from sqlalchemy import func, select

from app.domain.behavior import BehaviorType
from app.models.behavior import Behavior
from app.repositories.behavior_abstract import CreateBehaviorData, DuplicateBehaviorNameError
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository

pytestmark = pytest.mark.integration

URL = "/behaviors"


def body(name="nuevo", code="go_to(1, 2)", behavior_type="playerBehavior"):
    return {"name": name, "code": code, "type": behavior_type}


def count_behaviors(db_session, user_id):
    return db_session.scalar(
        select(func.count()).select_from(Behavior).where(Behavior.user_id == user_id)
    )


@pytest.mark.parametrize("behavior_type", ["playerBehavior", "coachBehavior"])
def test_creates_a_behavior_of_each_type(login, behavior_type):
    api = login(1)

    r = api.post(URL, json=body(code="x = ball_position()", behavior_type=behavior_type))

    assert r.status_code == 201
    created = r.json()
    assert created == {
        "id": created["id"],
        "name": "nuevo",
        "type": behavior_type,
        "code": "x = ball_position()",
    }
    assert api.get(f"{URL}/{created['id']}").json() == created


def test_without_session_is_401(client, db_session):
    r = client.post(URL, json=body())

    assert r.status_code == 401
    assert db_session.scalar(select(func.count()).select_from(Behavior)) == 0


def test_broken_json_has_the_three_fields_required(login):
    r = login(1).post(URL, content="{roto", headers={"Content-Type": "application/json"})

    assert r.status_code == 400
    assert r.json()["errors"] == [
        {"field": "name", "reason": "required"},
        {"field": "code", "reason": "required"},
        {"field": "type", "reason": "required"},
    ]


def test_a_name_the_user_already_has_in_the_other_type_is_duplicate(
    login, make_behaviors, db_session
):
    make_behaviors(1, ["Delantero"])  # playerBehavior
    make_behaviors(2, ["Mio"])

    r = login(1).post(URL, json=body(name="Delantero", behavior_type="coachBehavior"))
    other_user = login(2).post(URL, json=body(name="Delantero"))

    assert r.status_code == 409
    assert r.json() == {
        "code": "duplicateName",
        "message": "Ya tenés un comportamiento con ese nombre.",
        "codeError": None,
    }
    assert other_user.status_code == 201
    assert count_behaviors(db_session, 1) == 1  # el rechazo no creó nada


def test_a_name_with_spaces_around_is_the_same_name(login, make_behaviors):
    make_behaviors(1, ["Delantero"])

    response = login(1).post(URL, json=body(name=" Delantero "))

    assert response.status_code == 409
    assert response.json()["code"] == "duplicateName"


@pytest.mark.parametrize(
    "code", ["x = 1\n" * 251, "x" * 20001], ids=["251 líneas", "20.001 caracteres"]
)
def test_a_code_too_long_is_409_without_location(login, db_session, code):
    r = login(1).post(URL, json=body(code=code))

    assert r.status_code == 409
    assert (r.json()["code"], r.json()["codeError"]) == ("codeTooLong", None)
    assert count_behaviors(db_session, 1) == 0


def test_an_invalid_code_for_its_type_reports_where(login, db_session):
    r = login(1).post(URL, json=body(code="x = 1\n  \nkick()", behavior_type="coachBehavior"))

    assert r.status_code == 409
    assert r.json()["code"] == "invalidCode"
    assert r.json()["codeError"] == {"rule": "primitiveNotAllowedForType", "line": 3, "column": 1}
    assert count_behaviors(db_session, 1) == 0


def test_the_unique_name_is_also_enforced_by_the_database(db_session, make_user):
    make_user(1)
    repository = SqlAlchemyBehaviorRepository(db_session)
    data = CreateBehaviorData(name="igual", code="", type=BehaviorType.player_behavior)
    repository.create(1, data)

    with pytest.raises(DuplicateBehaviorNameError):
        repository.create(1, data)

    assert repository.name_taken(1, "igual")  # la sesión sigue usable después del rollback


def test_create_many_keeps_the_type_of_each_behavior(db_session, make_user):
    make_user(1)
    coach = CreateBehaviorData(name="DT", code="", type=BehaviorType.coach_behavior)

    created = SqlAlchemyBehaviorRepository(db_session).create_many(1, [coach])

    assert created[0].type == BehaviorType.coach_behavior
