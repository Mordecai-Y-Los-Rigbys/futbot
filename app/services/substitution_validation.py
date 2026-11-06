from dataclasses import dataclass


@dataclass(frozen=True)
class SubstituteInput:
    starter_id: int | None
    substitute_id: int | None


def parse_substitute(body: object) -> tuple[SubstituteInput, list[dict[str, str]]]:
    """Valida ambos IDs; conserva los campos válidos para sus reglas propias."""
    data = body if isinstance(body, dict) else {}
    errors: list[dict[str, str]] = []
    values: dict[str, int | None] = {}

    for field in ("starterId", "substituteId"):
        if field not in data:
            errors.append({"field": field, "reason": "required"})
            values[field] = None
            continue
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append({"field": field, "reason": "invalidType"})
            values[field] = None
            continue
        if not 1 <= value <= 2_147_483_647:
            errors.append({"field": field, "reason": "outOfRange"})
            values[field] = None
            continue
        values[field] = value

    return SubstituteInput(values["starterId"], values["substituteId"]), errors
