import copy

import pytest

from app.errors import ApiError
from app.services.friendly_validation import parse_create_friendly
from app.services.league_validation import INVALID_JSON

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


def valid():
    return {
        "name": "Partido amistoso 1",
        "members": [
            {"playerId": i + 1, "role": r, "behaviorId": 10 + i} for i, r in enumerate(ROLES)
        ],
    }


def code_of(body):
    with pytest.raises(ApiError) as e:
        parse_create_friendly(body)
    assert e.value.status_code == 400
    return e.value.code


def mutated(fn):
    b = valid()
    fn(b)
    return b


def test_valid_body_is_parsed():
    data = parse_create_friendly(valid())
    assert data.name == "Partido amistoso 1" and len(data.members) == 6


def test_name_of_20_chars_is_accepted_and_21_rejected():
    assert parse_create_friendly(mutated(lambda b: b.update(name="x" * 20)))
    assert code_of(mutated(lambda b: b.update(name="x" * 21))) == "nameTooLong"


@pytest.mark.parametrize("body", [INVALID_JSON, [], "x", 5])
def test_non_object_body_is_invalid_field_type(body):
    assert code_of(body) == "invalidFieldType"


@pytest.mark.parametrize(
    "fn",
    [
        lambda b: b.update(name=5),
        lambda b: b.update(name=None),
        lambda b: b.update(members="x"),
        lambda b: b["members"].__setitem__(0, "x"),
        lambda b: b["members"][0].update(role=1),
        lambda b: b["members"][0].update(playerId="1"),
        lambda b: b["members"][0].update(playerId=True),
        lambda b: b["members"][0].update(playerId=0),
        lambda b: b["members"][0].update(behaviorId=2147483648),
        lambda b: b["members"][0].update(behaviorId=1.5),
    ],
)
def test_invalid_field_type(fn):
    assert code_of(mutated(fn)) == "invalidFieldType"


@pytest.mark.parametrize(
    "fn",
    [
        lambda b: b.pop("name"),
        lambda b: b.pop("members"),
        lambda b: b.update(name=""),
        lambda b: b["members"][0].pop("playerId"),
        lambda b: b["members"][0].pop("role"),
        lambda b: b["members"][0].pop("behaviorId"),
    ],
)
def test_incomplete_form(fn):
    assert code_of(mutated(fn)) == "incompleteForm"


def test_empty_body_is_incomplete_form():
    assert code_of(None) == "incompleteForm"
    assert code_of({}) == "incompleteForm"


@pytest.mark.parametrize(
    "fn",
    [
        lambda b: b["members"].pop(),
        lambda b: b["members"].append({"playerId": 7, "role": "substitute", "behaviorId": 1}),
        lambda b: b["members"][0].update(role="goalkeeper"),
        lambda b: b["members"][0].update(role="midfield"),  # 2 midfield, 0 forward
        lambda b: b["members"][5].update(role="forward"),  # 2 forward, 2 substitute
        lambda b: b["members"][1].update(playerId=1),  # playerId repetido
    ],
)
def test_invalid_team(fn):
    assert code_of(mutated(fn)) == "invalidTeam"


def test_precedence_type_over_incomplete_over_name_over_team():
    b = valid()
    b["name"] = "x" * 21
    b["members"].pop()  # invalidTeam
    assert code_of(copy.deepcopy(b)) == "nameTooLong"
    b["members"][0].pop("role")  # incompleteForm
    assert code_of(copy.deepcopy(b)) == "incompleteForm"
    b["members"][1]["playerId"] = "x"  # invalidFieldType
    assert code_of(copy.deepcopy(b)) == "invalidFieldType"
