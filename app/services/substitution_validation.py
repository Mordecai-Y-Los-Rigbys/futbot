from dataclasses import dataclass
from typing import Any

from app.services.field_validation import (
    FieldErrors,
    all_required,
    field_error,
    id_reason,
    is_readable,
)

FIELDS = ("starterId", "substituteId")


@dataclass(frozen=True)
class SubstituteInput:
    starter_id: int | None  # None si el campo es inválido
    substitute_id: int | None


def parse_substitute(body: Any) -> tuple[SubstituteInput, FieldErrors]:
    """Valida los dos ids sin cortar en el primer error. Devuelve también los ids
    válidos (None el inválido), para que cada uno se chequee contra el equipo."""
    if not is_readable(body):
        return SubstituteInput(None, None), all_required(FIELDS)

    reasons = {field: id_reason(body, field) for field in FIELDS}
    errors = [field_error(field, reason) for field, reason in reasons.items() if reason]
    request = SubstituteInput(
        starter_id=None if reasons["starterId"] else body["starterId"],
        substitute_id=None if reasons["substituteId"] else body["substituteId"],
    )
    return request, errors
