import re

from app.errors import ValidationApiError
from app.helpers.ids import MAX_ID

MAX_PAGE = MAX_ID
_INT_RE = re.compile(r"-?[0-9]+")


def _page_reason(raw: str) -> str | None:
    if not _INT_RE.fullmatch(raw):
        return "invalidType"
    digits = raw.lstrip("-").lstrip("0")
    # El largo se mira antes de int()
    if raw.startswith("-") or digits == "" or len(digits) > len(str(MAX_PAGE)):
        return "outOfRange"
    if int(digits) > MAX_PAGE:
        return "outOfRange"
    return None


def parse_page(raw: str) -> int:
    """`page` de los listados paginados (convención 4).

    Raises:
        ValidationApiError 400: `page` con invalidType si no es un entero, o
            outOfRange si queda fuera de 1..MAX_PAGE.
    """
    reason = _page_reason(raw)
    if reason:
        raise ValidationApiError([{"field": "page", "reason": reason}])
    return int(raw)
