import pytest
from app.errors import ApiError
from app.services.player_validation import INVALID_JSON, parse_create_player, CreatePlayerData


def valid_payload():
    return {
        "name": "Lionel Messi",
        "power": 60,
        "agility": 70,
        "control": 80,
        "strength": 40,
        "speed": 50,
    }


def test_parse_create_player_success():
    payload = valid_payload()
    result = parse_create_player(payload)

    assert isinstance(result, CreatePlayerData)
    assert result.name == "Lionel Messi"
    assert result.power == 60
    assert result.speed == 50


@pytest.mark.parametrize(
    "invalid_body",
    [
        INVALID_JSON,
        [],
        "string_body",
    ],
)
def test_parse_create_player_invalid_json(invalid_body):
    with pytest.raises(ApiError) as exc:
        parse_create_player(invalid_body)
    assert exc.value.status_code == 400
    assert exc.value.code == "invalidFieldType"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("name", 123),
        ("name", None),
        ("power", "sesenta"),
        ("power", None),
        ("agility", True),
        ("control", 10.5),
    ],
)
def test_parse_create_player_invalid_field_type(field, bad_value):
    payload = valid_payload()
    payload[field] = bad_value

    with pytest.raises(ApiError) as exc:
        parse_create_player(payload)
    assert exc.value.code == "invalidFieldType"


@pytest.mark.parametrize(
    "missing_field", ["name", "power", "agility", "control", "strength", "speed"]
)
def test_parse_create_player_missing_fields(missing_field):
    payload = valid_payload()
    del payload[missing_field]

    with pytest.raises(ApiError) as exc:
        parse_create_player(payload)
    assert exc.value.code == "incompleteForm"


def test_parse_create_player_empty_name():
    payload = valid_payload()
    payload["name"] = "   "

    with pytest.raises(ApiError) as exc:
        parse_create_player(payload)
    assert exc.value.code == "incompleteForm"


def test_parse_create_player_name_too_long():
    payload = valid_payload()
    payload["name"] = "A" * 21

    with pytest.raises(ApiError) as exc:
        parse_create_player(payload)
    assert exc.value.code == "nameTooLong"


@pytest.mark.parametrize(
    "stat_name,bad_value",
    [
        ("power", 19),
        ("speed", 101),
    ],
)
def test_parse_create_player_stat_out_of_range(stat_name, bad_value):
    payload = valid_payload()
    payload[stat_name] = bad_value
    diff = 60 - bad_value
    payload["agility"] = payload["agility"] + diff

    with pytest.raises(ApiError) as exc:
        parse_create_player(payload)
    assert exc.value.code == "statOutOfRange"


def test_parse_create_player_invalid_stat_sum():
    payload = valid_payload()
    payload["power"] = 80  # Suma = 320

    with pytest.raises(ApiError) as exc:
        parse_create_player(payload)
    assert exc.value.code == "statSumMismatch"


def test_parse_create_player_rule_precedence():
    # Tipo inválido + falta campo -> invalidFieldType
    payload_type_and_missing = {"power": "sesenta"}
    with pytest.raises(ApiError) as exc:
        parse_create_player(payload_type_and_missing)
    assert exc.value.code == "invalidFieldType"

    # Falta campo + stat fuera de rango -> incompleteForm
    payload_missing_and_range = {
        "name": "Messi",
        "power": 150,
        "agility": 60,
        "control": 60,
        "strength": 60,
        # falta speed
    }
    with pytest.raises(ApiError) as exc:
        parse_create_player(payload_missing_and_range)
    assert exc.value.code == "incompleteForm"

    # Nombre muy largo + stat fuera de rango -> nameTooLong
    payload_name_and_range = valid_payload()
    payload_name_and_range["name"] = "A" * 25
    payload_name_and_range["power"] = 150
    with pytest.raises(ApiError) as exc:
        parse_create_player(payload_name_and_range)
    assert exc.value.code == "nameTooLong"

    # Stat fuera de rango + suma inválida -> statOutOfRange
    payload_range_and_sum = valid_payload()
    payload_range_and_sum["power"] = 150
    with pytest.raises(ApiError) as exc:
        parse_create_player(payload_range_and_sum)
    assert exc.value.code == "statOutOfRange"
