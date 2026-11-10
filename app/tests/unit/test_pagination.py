import pytest

from app.api.pagination import MAX_PAGE, parse_page
from app.errors import ValidationApiError


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", 1),
        ("2", 2),
        ("50", 50),
        ("007", 7),  # ceros a la izquierda: sigue siendo un entero
        (str(MAX_PAGE), MAX_PAGE),  # límite superior válido
    ],
)
def test_parse_page_valid(raw, expected):
    assert parse_page(raw) == expected


def _assert_page_error(raw: str, reason: str):
    with pytest.raises(ValidationApiError) as exc_info:
        parse_page(raw)
    err = exc_info.value
    assert (err.status_code, err.code) == (400, "invalidFields")
    assert err.errors == [{"field": "page", "reason": reason}]
    assert err.message


@pytest.mark.parametrize(
    "raw",
    [
        "abc",
        "1.5",
        "",  # ?page= vacío
        " 1",
        "1 ",
        "1e3",
        "0x10",
        "-",
        "--1",
        "+1",
        "１２",  # dígitos de ancho completo: no son [0-9]
    ],
)
def test_parse_page_not_an_integer_is_invalid_type(raw):
    _assert_page_error(raw, "invalidType")


@pytest.mark.parametrize(
    "raw", ["0", "000", "-0", "-1", "-100", str(MAX_PAGE + 1), "99999999999", "00" + str(MAX_PAGE + 1)]
)
def test_parse_page_out_of_range(raw):
    _assert_page_error(raw, "outOfRange")


def test_parse_page_huge_digit_string_is_out_of_range():
    # Más dígitos que el límite de int() de Python (4300 por defecto)
    _assert_page_error("9" * 5000, "outOfRange")


def test_parse_page_huge_negative_digit_string_is_out_of_range():
    _assert_page_error("-" + "9" * 5000, "outOfRange")


def test_parse_page_leading_zeros_do_not_count_as_digits():
    assert parse_page("0" * 20 + "5") == 5
