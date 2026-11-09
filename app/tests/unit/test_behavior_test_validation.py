"""Body de POST /behaviors/{id}/test-connections (convenciones 6 y 9)."""

import pytest

from app.errors import ValidationApiError
from app.services.behavior_test_validation import LineupMemberInput, parse_behavior_test
from app.services.field_validation import INVALID_JSON

LINEUP = [
    ("club1", "forward"),
    ("club1", "midfield"),
    ("club1", "defense"),
    ("club2", "forward"),
    ("club2", "midfield"),
    ("club2", "defense"),
]
MISSING = object()


def members():
    return [
        {"playerId": i + 1, "club": club, "role": role, "behaviorId": 10}
        for i, (club, role) in enumerate(LINEUP)
    ]


def errors_of(body):
    with pytest.raises(ValidationApiError) as exc:
        parse_behavior_test(body)
    return [(e["field"], e["reason"]) for e in exc.value.errors]


def test_valid_lineup_is_parsed_in_order():
    parsed = parse_behavior_test({"members": members(), "otro": 1})
    assert parsed == [
        LineupMemberInput(i + 1, club, role, 10) for i, (club, role) in enumerate(LINEUP)
    ]


@pytest.mark.parametrize("body", [None, INVALID_JSON, [], "x", 5, {}])
def test_unreadable_body_or_missing_members_is_required(body):
    assert errors_of(body) == [("members", "required")]


@pytest.mark.parametrize("value", [None, {}, "x", 6])
def test_members_that_is_not_an_array_is_invalid_type(value):
    assert errors_of({"members": value}) == [("members", "invalidType")]


@pytest.mark.parametrize(
    "key, value, reason",
    [
        ("playerId", MISSING, "required"),
        ("playerId", "1", "invalidType"),
        ("playerId", 1.5, "invalidType"),
        ("playerId", True, "invalidType"),
        ("playerId", None, "invalidType"),
        ("playerId", 0, "outOfRange"),
        ("playerId", 2147483648, "outOfRange"),
        ("club", MISSING, "required"),
        ("club", 1, "invalidType"),
        ("club", None, "invalidType"),
        ("role", MISSING, "required"),
        ("role", ["forward"], "invalidType"),
        ("behaviorId", MISSING, "required"),
        ("behaviorId", "abc", "invalidType"),
        ("behaviorId", -1, "outOfRange"),
    ],
)
def test_field_errors(key, value, reason):
    body = members()
    if value is MISSING:
        del body[2][key]
    else:
        body[2][key] = value
    assert errors_of({"members": body}) == [(f"members[2].{key}", reason)]


def test_element_that_is_not_an_object_is_invalid_type():
    body = members()
    body[1] = 7
    assert errors_of({"members": body}) == [("members[1]", "invalidType")]


def test_all_errors_are_reported_in_schema_order():
    body = members()
    body[0] = {"club": 3, "behaviorId": 0}
    body[4] = "x"
    assert errors_of({"members": body}) == [
        ("members[0].playerId", "required"),
        ("members[0].club", "invalidType"),
        ("members[0].role", "required"),
        ("members[0].behaviorId", "outOfRange"),
        ("members[4]", "invalidType"),
    ]


def test_invalid_team_is_not_evaluated_if_a_field_fails():
    body = members()[:3]
    body[0]["playerId"] = "x"
    assert errors_of({"members": body}) == [("members[0].playerId", "invalidType")]


def with_change(index, **changes):
    def _apply(lineup):
        lineup[index] = {**lineup[index], **changes}
        return lineup

    return _apply


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m[:5],
        lambda m: m + [{**m[0], "playerId": 99}],
        lambda m: [],
        with_change(5, playerId=1),
        with_change(4, role="forward"),
        with_change(3, club="club1"),
        with_change(0, club="club3"),
        with_change(0, role="substitute"),
        with_change(0, role="goalkeeper"),
    ],
    ids=[
        "menos de 6",
        "más de 6",
        "vacío",
        "jugador repetido",
        "rol repetido en un club",
        "club con 4 jugadores",
        "club fuera del enum",
        "suplente",
        "rol fuera del enum",
    ],
)
def test_invalid_team(change):
    assert errors_of({"members": change(members())}) == [("members", "invalidTeam")]
