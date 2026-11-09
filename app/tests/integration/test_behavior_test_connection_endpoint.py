"""POST /behaviors/{id}/test-connections contra la base real (Postgres)."""

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.behavior import BehaviorType
from app.models.behavior import Behavior
from app.models.behavior_test_token import BehaviorTestToken
from app.models.player import Player
from app.schemas import errors as schemas

pytestmark = pytest.mark.integration

MAX_ID = 2147483647
LINEUP = [
    ("club1", "forward"),
    ("club1", "midfield"),
    ("club1", "defense"),
    ("club2", "forward"),
    ("club2", "midfield"),
    ("club2", "defense"),
]


# --- fixtures y helpers -------------------------------------------------------


@pytest.fixture()
def owner(create_user):
    return create_user("owner")


@pytest.fixture()
def other(create_user):
    return create_user("other")


@pytest.fixture()
def make_behavior(db_session):
    numbers = itertools.count(1)  # cada behavior con su nombre: no se repiten por usuario

    def _make(user, type=BehaviorType.player_behavior):
        record = Behavior(user_id=user.id, name=f"b{next(numbers)}", code="pass", type=type)
        db_session.add(record)
        db_session.commit()
        return record

    return _make


@pytest.fixture()
def make_players(db_session):
    def _make(user, count=6):
        players = [
            Player(
                user_id=user.id,
                name=f"J{i}",
                power=60,
                agility=60,
                control=60,
                strength=60,
                speed=60,
            )
            for i in range(count)
        ]
        db_session.add_all(players)
        db_session.commit()
        return [p.id for p in players]

    return _make


@pytest.fixture()
def behavior(owner, make_behavior):
    return make_behavior(owner)


@pytest.fixture()
def player_ids(owner, make_players):
    return make_players(owner)


def lineup(player_ids, behavior_id):
    return {
        "members": [
            {"playerId": p, "club": club, "role": role, "behaviorId": behavior_id}
            for p, (club, role) in zip(player_ids, LINEUP)
        ]
    }


@pytest.fixture()
def body(player_ids, behavior):
    return lineup(player_ids, behavior.id)


def members_of(body):
    return [dict(m) for m in body["members"]]


def url(behavior_id):
    return f"/behaviors/{behavior_id}/test-connections"


def tokens_of(db_session):
    db_session.expire_all()
    return list(db_session.scalars(select(BehaviorTestToken)))


def codes(resp):
    return [(e["field"], e["reason"]) for e in resp.json()["errors"]]


def as_utc(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc)


# --- 201 ----------------------------------------------------------------------


def test_201_saves_the_token_with_the_user_the_behavior_and_the_lineup(
    login_as, db_session, owner, behavior, body
):
    before = datetime.now(timezone.utc)

    resp = login_as(owner).post(url(behavior.id), json=body)

    assert resp.status_code == 201, resp.text
    [saved] = tokens_of(db_session)
    assert saved.token == resp.json()["tokenWs"]
    assert (saved.user_id, saved.behavior_id) == (owner.id, behavior.id)
    after = datetime.now(timezone.utc)
    assert before + timedelta(minutes=5) <= as_utc(saved.expires_at) <= after + timedelta(minutes=5)
    assert saved.members == [
        {
            "player_id": m["playerId"],
            "club": m["club"],
            "role": m["role"],
            "behavior_id": m["behaviorId"],
        }
        for m in body["members"]
    ]


def test_the_route_behavior_does_not_have_to_be_in_the_lineup(
    login_as, owner, behavior, player_ids, make_behavior
):
    another = make_behavior(owner)
    resp = login_as(owner).post(url(behavior.id), json=lineup(player_ids, another.id))
    assert resp.status_code == 201, resp.text


def test_each_request_creates_a_new_token(login_as, db_session, owner, behavior, body):
    api = login_as(owner)
    first = api.post(url(behavior.id), json=body).json()["tokenWs"]
    second = api.post(url(behavior.id), json=body).json()["tokenWs"]
    assert first != second
    assert {t.token for t in tokens_of(db_session)} == {first, second}


def test_unknown_fields_are_ignored(login_as, owner, behavior, body):
    resp = login_as(owner).post(url(behavior.id), json={**body, "behaviorId": 999})
    assert resp.status_code == 201, resp.text


# --- 401 ----------------------------------------------------------------------


def test_no_session_is_401(client, behavior, body):
    resp = client.post(url(behavior.id), json=body)
    assert resp.status_code == 401 and resp.json()["code"] is None


def test_expired_session_is_401(login_as, owner, behavior, body):
    resp = login_as(owner, expires_in=timedelta(days=-1)).post(url(behavior.id), json=body)
    assert resp.status_code == 401 and resp.json()["code"] is None


# --- 404 ----------------------------------------------------------------------


@pytest.mark.parametrize("raw_id", [str(MAX_ID), "abc", "0", "-1", "1.5", "2147483648"])
def test_unknown_or_invalid_behavior_is_404(login_as, db_session, owner, body, raw_id):
    resp = login_as(owner).post(url(raw_id), json=body)
    assert resp.status_code == 404 and resp.json()["code"] is None
    assert tokens_of(db_session) == []


# --- 400 ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"content": "{", "headers": {"Content-Type": "application/json"}},
        {"json": []},
        {"json": "x"},
        {"json": {}},
    ],
    ids=["vacío", "json inválido", "array", "string", "sin members"],
)
def test_unreadable_body_or_missing_members_is_required(
    login_as, db_session, owner, behavior, kwargs
):
    resp = login_as(owner).post(url(behavior.id), **kwargs)
    assert resp.status_code == 400
    schemas.ValidationBadRequest.model_validate(resp.json())
    assert codes(resp) == [("members", "required")]
    assert tokens_of(db_session) == []


def test_members_that_is_not_an_array_is_invalid_type(login_as, owner, behavior):
    resp = login_as(owner).post(url(behavior.id), json={"members": 5})
    assert resp.status_code == 400 and codes(resp) == [("members", "invalidType")]


def test_all_field_errors_are_reported_in_order(login_as, db_session, owner, behavior, body):
    members = members_of(body)
    members[0]["playerId"] = "abc"
    members[1]["club"] = 1
    del members[3]["role"]
    members[4] = "x"
    members[5]["behaviorId"] = 2147483648

    resp = login_as(owner).post(url(behavior.id), json={"members": members})

    assert resp.status_code == 400
    assert codes(resp) == [
        ("members[0].playerId", "invalidType"),
        ("members[1].club", "invalidType"),
        ("members[3].role", "required"),
        ("members[4]", "invalidType"),
        ("members[5].behaviorId", "outOfRange"),
    ]
    assert tokens_of(db_session) == []


@pytest.mark.parametrize(
    "change",
    [
        lambda m: [m[0], {**m[1], "role": "forward"}, *m[2:]],
        lambda m: [*m[:5], {**m[5], "playerId": m[0]["playerId"]}],
        lambda m: m[:5],
        lambda m: [{**m[0], "club": "club3"}, *m[1:]],
    ],
    ids=["rol repetido en un club", "jugador repetido", "menos de 6", "club fuera del enum"],
)
def test_invalid_team(login_as, db_session, owner, behavior, body, change):
    resp = login_as(owner).post(url(behavior.id), json={"members": change(members_of(body))})
    assert resp.status_code == 400 and codes(resp) == [("members", "invalidTeam")]
    assert tokens_of(db_session) == []


# --- 403 ----------------------------------------------------------------------


def test_behavior_of_another_user_is_403(login_as, db_session, owner, other, make_behavior, body):
    resp = login_as(owner).post(url(make_behavior(other).id), json=body)
    assert resp.status_code == 403 and resp.json()["code"] is None
    assert tokens_of(db_session) == []


# --- 409 ----------------------------------------------------------------------


def test_coach_behavior_is_409_not_player_behavior(
    login_as, db_session, owner, make_behavior, body
):
    coach = make_behavior(owner, BehaviorType.coach_behavior)
    resp = login_as(owner).post(url(coach.id), json=body)
    assert resp.status_code == 409
    schemas.TestBehaviorConflict.model_validate(resp.json())
    assert resp.json()["code"] == "notPlayerBehavior"
    assert tokens_of(db_session) == []


@pytest.mark.parametrize(
    "target", ["jugador ajeno", "behavior ajeno", "jugador inexistente", "behavior inexistente"]
)
def test_lineup_not_owned_is_409(
    login_as, db_session, owner, other, behavior, body, make_players, make_behavior, target
):
    members = members_of(body)
    if target == "jugador ajeno":
        members[0]["playerId"] = make_players(other, 1)[0]
    elif target == "behavior ajeno":
        members[0]["behaviorId"] = make_behavior(other).id
    elif target == "jugador inexistente":
        members[0]["playerId"] = MAX_ID
    else:
        members[0]["behaviorId"] = MAX_ID

    resp = login_as(owner).post(url(behavior.id), json={"members": members})

    assert resp.status_code == 409 and resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert tokens_of(db_session) == []


def test_coach_behavior_in_the_lineup_is_409_type_mismatch(
    login_as, db_session, owner, behavior, body, make_behavior
):
    members = members_of(body)
    members[2]["behaviorId"] = make_behavior(owner, BehaviorType.coach_behavior).id
    resp = login_as(owner).post(url(behavior.id), json={"members": members})
    assert resp.status_code == 409 and resp.json()["code"] == "behaviorTypeMismatch"
    assert tokens_of(db_session) == []


# --- varias fallas a la vez: 401 > 404 > 400 > 403 > 409 ----------------------


def test_401_beats_404(client):
    assert client.post(url("abc"), json={"members": 5}).status_code == 401


def test_404_beats_400(login_as, owner):
    assert login_as(owner).post(url(MAX_ID), json={"members": "x"}).status_code == 404


def test_400_beats_403(login_as, owner, other, make_behavior):
    resp = login_as(owner).post(url(make_behavior(other).id), json={"members": []})
    assert resp.status_code == 400 and codes(resp) == [("members", "invalidTeam")]


def test_403_beats_409(login_as, owner, other, make_behavior, body):
    foreign_coach = make_behavior(other, BehaviorType.coach_behavior)
    assert login_as(owner).post(url(foreign_coach.id), json=body).status_code == 403


def test_not_player_behavior_beats_the_other_409(
    login_as, owner, other, make_behavior, make_players, body
):
    coach = make_behavior(owner, BehaviorType.coach_behavior)
    members = members_of(body)
    members[0]["playerId"] = make_players(other, 1)[0]
    members[1]["behaviorId"] = coach.id
    resp = login_as(owner).post(url(coach.id), json={"members": members})
    assert resp.json()["code"] == "notPlayerBehavior"


def test_not_owned_beats_type_mismatch(
    login_as, owner, other, behavior, make_behavior, make_players, body
):
    members = members_of(body)
    members[0]["playerId"] = make_players(other, 1)[0]
    members[1]["behaviorId"] = make_behavior(owner, BehaviorType.coach_behavior).id
    resp = login_as(owner).post(url(behavior.id), json={"members": members})
    assert resp.json()["code"] == "playerOrBehaviorNotOwned"
