import pytest

from app.errors import ValidationApiError
from app.services.friendly_validation import parse_create_friendly
from app.services.league_validation import INVALID_JSON
from app.tests.unit.member_cases import MEMBERS_IDS, MEMBERS_PARAMS, MISSING, TEAM, err


def valid(**over):
    body = {"name": "Partido amistoso 1", "members": [dict(m) for m in TEAM]}
    for key, value in over.items():
        if value is MISSING:
            body.pop(key)
        else:
            body[key] = value
    return body


def errors_of(body):
    with pytest.raises(ValidationApiError) as e:
        parse_create_friendly(body)
    assert (e.value.status_code, e.value.code) == (400, "invalidFields")
    return e.value.errors


def test_valid_body_is_parsed():
    data = parse_create_friendly(valid())
    assert data.name == "Partido amistoso 1" and len(data.members) == 6


def test_name_of_20_chars_is_accepted():
    assert parse_create_friendly(valid(name="x" * 20))


@pytest.mark.parametrize("body", [INVALID_JSON, None, {}, [], "x", 5])
def test_unreadable_body_reports_name_and_members_required(body):
    assert errors_of(body) == [err("name", "required"), err("members", "required")]


@pytest.mark.parametrize(
    "value, reason",
    [
        (MISSING, "required"),
        ("", "required"),
        (5, "invalidType"),
        (None, "invalidType"),
        ("x" * 21, "tooLong"),
    ],
)
def test_name_reasons(value, reason):
    assert errors_of(valid(name=value)) == [err("name", reason)]


@pytest.mark.parametrize("members, expected", MEMBERS_PARAMS, ids=MEMBERS_IDS)
def test_members_reasons(members, expected):
    assert errors_of(valid(members=members)) == expected


def test_name_and_members_errors_are_reported_together():
    body = valid(name="x" * 21, members=TEAM[:5])
    assert errors_of(body) == [err("name", "tooLong"), err("members", "invalidTeam")]
