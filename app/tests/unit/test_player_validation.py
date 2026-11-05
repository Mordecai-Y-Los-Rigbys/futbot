import pytest

from app.errors import ValidationApiError
from app.services.player_validation import (
    INVALID_JSON,
    STATS,
    CreatePlayerData,
    parse_create_player,
)

MISSING = object()


def valid_payload(**over):
    payload = {
        "name": "Lionel Messi",
        "power": 60,
        "agility": 70,
        "control": 80,
        "strength": 40,
        "speed": 50,
    }
    for key, value in over.items():
        if value is MISSING:
            payload.pop(key)
        else:
            payload[key] = value
    return payload


def errors_of(body):
    with pytest.raises(ValidationApiError) as exc:
        parse_create_player(body)
    assert (exc.value.status_code, exc.value.code) == (400, "invalidFields")
    assert exc.value.message
    return exc.value.errors


def err(field, reason):
    return {"field": field, "reason": reason}


def test_parse_create_player_success():
    result = parse_create_player(valid_payload())

    assert isinstance(result, CreatePlayerData)
    assert result.name == "Lionel Messi"
    assert result.power == 60
    assert result.speed == 50


def test_name_is_stored_without_surrounding_spaces():
    assert parse_create_player(valid_payload(name="  Messi  ")).name == "Messi"


def test_boundaries_are_valid():
    assert parse_create_player(valid_payload(name="x" * 20))
    assert parse_create_player(
        valid_payload(power=100, agility=100, control=20, strength=20, speed=60)
    )


# --- body ilegible (convención 9) ---------------------------------------------


@pytest.mark.parametrize("body", [INVALID_JSON, None, [], [1], "string_body", 42, True])
def test_unreadable_body_reports_every_field_as_required(body):
    assert errors_of(body) == [err(f, "required") for f in ("name", *STATS)]


def test_empty_object_reports_every_field_as_required():
    assert errors_of({}) == [err(f, "required") for f in ("name", *STATS)]


# --- un reason por campo --------------------------------------------------------


@pytest.mark.parametrize(
    "value, reason",
    [
        (MISSING, "required"),
        ("", "required"),
        ("   ", "required"),
        (123, "invalidType"),
        (None, "invalidType"),
        (["Messi"], "invalidType"),
        ("A" * 21, "tooLong"),
        ("  " + "A" * 21 + "  ", "tooLong"),
    ],
)
def test_name_reasons(value, reason):
    assert errors_of(valid_payload(name=value)) == [err("name", reason)]


def test_name_length_is_measured_after_trimming():
    assert parse_create_player(valid_payload(name="  " + "A" * 20 + "  ")).name == "A" * 20


@pytest.mark.parametrize("stat", STATS)
@pytest.mark.parametrize(
    "value, reason",
    [
        (MISSING, "required"),
        ("sesenta", "invalidType"),
        ("60", "invalidType"),
        (None, "invalidType"),
        (True, "invalidType"),
        (60.0, "invalidType"),
        (10.5, "invalidType"),
        (19, "outOfRange"),
        (101, "outOfRange"),
        (-1, "outOfRange"),
    ],
)
def test_stat_reasons(stat, value, reason):
    # Si una stat falla, la suma no se evalúa: solo aparece el error de la stat
    assert errors_of(valid_payload(**{stat: value})) == [err(stat, reason)]


def test_invalid_sum_when_every_stat_is_valid():
    assert errors_of(valid_payload(power=80)) == [err("stats", "invalidSum")]  # suma 320


def test_invalid_sum_is_not_evaluated_if_a_stat_fails():
    assert errors_of(valid_payload(power=150, agility=20)) == [err("power", "outOfRange")]


# --- varios campos a la vez -----------------------------------------------------


def test_all_failures_are_reported_in_schema_order():
    body = {
        "name": "A" * 25,
        "power": "x",
        # falta agility
        "control": 10,
        "strength": None,
        "speed": 150,
    }
    assert errors_of(body) == [
        err("name", "tooLong"),
        err("power", "invalidType"),
        err("agility", "required"),
        err("control", "outOfRange"),
        err("strength", "invalidType"),
        err("speed", "outOfRange"),
    ]


def test_invalid_sum_goes_after_the_stats():
    assert errors_of(valid_payload(name=5, power=80)) == [
        err("name", "invalidType"),
        err("stats", "invalidSum"),
    ]


def test_unknown_fields_are_ignored():
    assert parse_create_player(valid_payload(extra="x", user_id=99))
