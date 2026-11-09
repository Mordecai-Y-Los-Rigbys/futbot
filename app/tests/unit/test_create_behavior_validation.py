import pytest

from app.domain.behavior import BehaviorType
from app.errors import ValidationApiError
from app.services.behavior_validation import MAX_NAME_LEN, parse_create_behavior
from app.services.league_validation import INVALID_JSON

VALID = {"name": "Delantero 2", "code": "go_to(1, 2)", "type": "coachBehavior"}


def errors_of(body):
    with pytest.raises(ValidationApiError) as exc:
        parse_create_behavior(body)
    return exc.value.errors


def test_a_valid_body_returns_the_data_with_its_type():
    data = parse_create_behavior(VALID)

    assert (data.name, data.code, data.type) == (
        "Delantero 2",
        "go_to(1, 2)",
        BehaviorType.coach_behavior,
    )


def test_a_name_at_the_length_limit_is_valid():
    assert parse_create_behavior({**VALID, "name": "a" * MAX_NAME_LEN}).name == "a" * MAX_NAME_LEN


def test_the_spaces_around_the_name_do_not_count_and_are_removed():
    name = "  " + "a" * MAX_NAME_LEN + " "
    assert parse_create_behavior({**VALID, "name": name}).name == "a" * MAX_NAME_LEN


@pytest.mark.parametrize("body", [INVALID_JSON, None, [], "texto"], ids=repr)
def test_an_unreadable_body_has_the_three_fields_required(body):
    assert errors_of(body) == [
        {"field": "name", "reason": "required"},
        {"field": "code", "reason": "required"},
        {"field": "type", "reason": "required"},
    ]


@pytest.mark.parametrize(
    "field, value, reason",
    [
        ("name", None, "invalidType"),
        ("name", 5, "invalidType"),
        ("name", "", "required"),
        ("name", "   ", "required"),
        ("name", "a" * (MAX_NAME_LEN + 1), "tooLong"),
        ("code", None, "invalidType"),
        ("code", ["go_to(1, 2)"], "invalidType"),
        ("type", None, "invalidType"),
        ("type", "dt", "invalidValue"),
        ("type", "PlayerBehavior", "invalidValue"),
    ],
)
def test_each_field_reports_its_reason(field, value, reason):
    assert errors_of({**VALID, field: value}) == [{"field": field, "reason": reason}]


@pytest.mark.parametrize("field", ["name", "code", "type"])
def test_a_missing_field_is_required(field):
    body = {key: value for key, value in VALID.items() if key != field}

    assert errors_of(body) == [{"field": field, "reason": "required"}]


def test_all_the_errors_come_in_the_order_of_the_schema():
    assert errors_of({"type": "dt", "code": 1}) == [
        {"field": "name", "reason": "required"},
        {"field": "code", "reason": "invalidType"},
        {"field": "type", "reason": "invalidValue"},
    ]

