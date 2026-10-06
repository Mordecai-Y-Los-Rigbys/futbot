import re

from app.errors import ApiError

MAX_ID = 2147483647
_ID_RE = re.compile(r"[0-9]{1,10}")  # solo dígitos ASCII, largo acotado


def parse_path_id(raw: str, not_found_message: str) -> int:
    """Un id que no puede identificar ningún recurso es un recurso inexistente (404)."""
    if _ID_RE.fullmatch(raw):
        value = int(raw)
        if 1 <= value <= MAX_ID:
            return value
    raise ApiError(404, None, not_found_message)
