import pytest

from app.errors import ValidationApiError
from app.services.behavior_validation import MAX_NAME_LEN, parse_update_behavior
from app.services.league_validation import INVALID_JSON

VALID = {"name": "Delantero 2", "code": "go_to(1, 2)"}


def errors_of(body):
    with pytest.raises(ValidationApiError) as exc:
        parse_update_behavior(body)
    return exc.value.errors


def test_a_valid_body_returns_name_and_code_and_ignores_the_type():
    data = parse_update_behavior({**VALID, "type": "dt"})

    assert data.model_dump() == {"name": "Delantero 2", "code": "go_to(1, 2)"}


@pytest.mark.parametrize("body", [INVALID_JSON, None, [], "texto"], ids=repr)
def test_an_unreadable_body_has_name_and_code_required(body):
    assert errors_of(body) == [
        {"field": "name", "reason": "required"},
        {"field": "code", "reason": "required"},
    ]


@pytest.mark.parametrize(
    "field, value, reason",
    [
        ("name", None, "invalidType"),
        ("name", "   ", "required"),
        ("name", "a" * (MAX_NAME_LEN + 1), "tooLong"),
        ("code", None, "invalidType"),
    ],
)
def test_each_field_reports_its_reason(field, value, reason):
    assert errors_of({**VALID, field: value}) == [{"field": field, "reason": reason}]


def test_missing_fields_are_required_in_the_order_of_the_schema():
    assert errors_of({"type": "playerBehavior"}) == [
        {"field": "name", "reason": "required"},
        {"field": "code", "reason": "required"},
    ]


def test_the_spaces_around_the_name_are_removed():
    assert parse_update_behavior({**VALID, "name": "  Delantero 2 "}).name == "Delantero 2"
