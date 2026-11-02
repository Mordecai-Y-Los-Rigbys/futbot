import pytest

from app.errors import ValidationApiError
from app.services.league_validation import INVALID_JSON
from app.services.match_behavior_validation import (
    ReassignBehaviorInput,
    parse_reassign_behavior,
)

VALID = {"playerId": 3, "behaviorId": 7}


def errors_of(body):
    with pytest.raises(ValidationApiError) as exc:
        parse_reassign_behavior(body)
    assert exc.value.code == "invalidFields"
    return exc.value.errors


def test_valid_body_returns_the_ids():
    assert parse_reassign_behavior(VALID) == ReassignBehaviorInput(3, 7)


def test_ids_at_the_limits_are_valid():
    assert parse_reassign_behavior({"playerId": 1, "behaviorId": 2147483647})


@pytest.mark.parametrize("body", [INVALID_JSON, None, []])
def test_unreadable_body_reports_both_fields_as_required(body):
    assert errors_of(body) == [
        {"field": "playerId", "reason": "required"},
        {"field": "behaviorId", "reason": "required"},
    ]


@pytest.mark.parametrize("field", ["playerId", "behaviorId"])
def test_missing_field_is_required(field):
    body = {k: v for k, v in VALID.items() if k != field}
    assert errors_of(body) == [{"field": field, "reason": "required"}]


@pytest.mark.parametrize("field", ["playerId", "behaviorId"])
@pytest.mark.parametrize(
    "value, reason",
    [
        ("abc", "invalidType"),
        (None, "invalidType"),
        (True, "invalidType"),
        (0, "outOfRange"),
        (2147483648, "outOfRange"),
    ],
)
def test_each_bad_value_has_its_reason(field, value, reason):
    assert errors_of({**VALID, field: value}) == [{"field": field, "reason": reason}]


def test_both_fields_wrong_are_reported_in_schema_order():
    assert errors_of({"behaviorId": 0, "playerId": "abc"}) == [
        {"field": "playerId", "reason": "invalidType"},
        {"field": "behaviorId", "reason": "outOfRange"},
    ]