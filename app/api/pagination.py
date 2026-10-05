import re

from app.errors import ApiError
from app.helpers.ids import MAX_ID

MAX_PAGE = MAX_ID
_INT_RE = re.compile(r"-?[0-9]+")


def parse_page(raw: str) -> int:
    if not _INT_RE.fullmatch(raw):
        raise ApiError(400, "pageNotAnInteger", "`page` debe ser un entero.")
    try:
        value = int(raw)
    except ValueError:  # cadenas de miles de dígitos (límite de int() en Python)
        if raw.startswith("-"):
            raise ApiError(400, "pageBelowMinimum", "`page` debe ser al menos 1.")
        else:
            raise ApiError(400, "pageTooLarge", f"`page` no puede superar {MAX_PAGE}.")
    if value < 1:
        raise ApiError(400, "pageBelowMinimum", "`page` debe ser al menos 1.")
    if value > MAX_PAGE:
        raise ApiError(400, "pageTooLarge", f"`page` no puede superar {MAX_PAGE}.")
    return value