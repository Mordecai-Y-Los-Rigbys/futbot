"""Reglas de campo compartidas por los parsers de body."""

from typing import Any

from app.helpers.ids import MAX_ID


def field_error(field: str, reason: str) -> dict[str, str]:
    return {"field": field, "reason": reason}


def is_int(value: Any) -> bool:
    # bool es subclase de int en Python, pero `true` no es un entero JSON.
    # 1.0 llega como float: tampoco es un entero.
    return isinstance(value, int) and not isinstance(value, bool)


def id_reason(container: dict, key: str) -> str | None:
    if key not in container:
        return "required"
    value = container[key]
    if not is_int(value):  # incluye null
        return "invalidType"
    if not 1 <= value <= MAX_ID:
        return "outOfRange"
    return None


def string_reason(container: dict, key: str) -> str | None:
    if key not in container:
        return "required"
    if not isinstance(container[key], str):  # incluye null
        return "invalidType"
    return None
