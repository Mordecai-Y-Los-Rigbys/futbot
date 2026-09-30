import pytest

from app.api.pagination import MAX_PAGE, parse_page
from app.errors import ApiError


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


def _assert_api_error(raw: str, code: str):
    with pytest.raises(ApiError) as exc_info:
        parse_page(raw)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == code
    assert exc_info.value.message  # no vacío


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
        "１２",  # dígitos de ancho completo: no son [0-9]
    ],
)
def test_parse_page_not_an_integer(raw):
    _assert_api_error(raw, "pageNotAnInteger")


@pytest.mark.parametrize("raw", ["0", "-0", "-1", "-100"])
def test_parse_page_below_minimum(raw):
    _assert_api_error(raw, "pageBelowMinimum")


@pytest.mark.parametrize("raw", [str(MAX_PAGE + 1), "99999999999"])
def test_parse_page_too_large(raw):
    _assert_api_error(raw, "pageTooLarge")


def test_parse_page_huge_digit_string_is_too_large():
    # Más dígitos que el límite de int() de Python (4300 por defecto).
    _assert_api_error("9" * 5000, "pageTooLarge")


def test_parse_page_huge_negative_digit_string_is_below_minimum():
    _assert_api_error("-" + "9" * 5000, "pageBelowMinimum")