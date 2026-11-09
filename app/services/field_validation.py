"""Partes comunes de los 400 `invalidFields`

Cada función de `*_reason` devuelve el `reason` de un campo o None si es
válido, respetando la precedencia required > invalidType > tooLong/outOfRange.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.helpers.ids import MAX_ID

INVALID_JSON = object()

REQUIRED_ROLES = {"forward": 1, "midfield": 1, "defense": 1, "substitute": 3}
TEAM_SIZE = 6

FieldErrors = list[dict[str, str]]


@dataclass(frozen=True)
class MemberInput:
    player_id: int
    behavior_id: int
    role: str


def field_error(field: str, reason: str) -> dict[str, str]:
    return {"field": field, "reason": reason}


def is_readable(body: Any) -> bool:
    """Convención 9: JSON roto, body vacío o algo que no es un objeto es ilegible."""
    return isinstance(body, dict)


def all_required(fields: tuple[str, ...] | list[str]) -> FieldErrors:
    return [field_error(f, "required") for f in fields]


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def str_reason(container: dict, key: str, max_len: int, strip: bool = False) -> str | None:
    """`""` cuenta como faltante. Con `strip`, también un string de solo espacios."""
    if key not in container:
        return "required"
    value = container[key]
    if not isinstance(value, str):  # incluye null
        return "invalidType"
    if strip:
        value = value.strip()
    if value == "":
        return "required"
    if len(value) > max_len:
        return "tooLong"
    return None


def string_reason(container: dict, key: str) -> str | None:
    if key not in container:
        return "required"
    if not isinstance(container[key], str):  # incluye null
        return "invalidType"
    return None


def int_reason(
    container: dict, key: str, low: int | None = None, high: int = MAX_ID
) -> str | None:
    if key not in container:
        return "required"
    value = container[key]
    if not is_int(value):  # incluye null
        return "invalidType"
    if (low is not None and value < low) or value > high:
        return "outOfRange"
    return None


def bool_reason(container: dict, key: str) -> str | None:
    if key not in container:
        return "required"
    if not isinstance(container[key], bool):
        return "invalidType"
    return None


def id_reason(container: dict, key: str) -> str | None:
    return int_reason(container, key, 1, MAX_ID)


def _role_reason(member: dict) -> str | None:
    # Un string que no es un rol válido NO es error de campo: es invalidTeam (6.h)
    if "role" not in member:
        return "required"
    if not isinstance(member["role"], str):
        return "invalidType"
    return None


def _member_errors(index: int, member: Any) -> FieldErrors:
    if not isinstance(member, dict):
        return [field_error(f"members[{index}]", "invalidType")]
    reasons = (
        ("playerId", id_reason(member, "playerId")),
        ("role", _role_reason(member)),
        ("behaviorId", id_reason(member, "behaviorId")),
    )
    return [field_error(f"members[{index}].{key}", reason) for key, reason in reasons if reason]


def _is_valid_team(members: list[dict]) -> bool:
    return (
        len(members) == TEAM_SIZE
        and dict(Counter(m["role"] for m in members)) == REQUIRED_ROLES
        and len({m["playerId"] for m in members}) == TEAM_SIZE
    )


def members_errors(body: dict) -> FieldErrors:
    if "members" not in body:
        return [field_error("members", "required")]
    members = body["members"]
    if not isinstance(members, list):  # incluye null
        return [field_error("members", "invalidType")]

    errors = [e for i, m in enumerate(members) for e in _member_errors(i, m)]
    # invalidTeam cruza campos: solo si ningún elemento tuvo errores (6.f)
    if not errors and not _is_valid_team(members):
        errors.append(field_error("members", "invalidTeam"))
    return errors


def to_members(raw: list[dict]) -> list[MemberInput]:
    return [MemberInput(m["playerId"], m["behaviorId"], m["role"]) for m in raw]
