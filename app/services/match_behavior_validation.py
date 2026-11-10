from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.services.field_validation import INVALID_JSON, field_error, id_reason

FIELDS = ("playerId", "behaviorId")


@dataclass(frozen=True)
class ReassignBehaviorInput:
    player_id: int
    behavior_id: int


def parse_reassign_behavior(body: Any) -> ReassignBehaviorInput:
    """Valida el body y devuelve los ids ya tipados."""
    if body is INVALID_JSON or not isinstance(body, dict):
        raise ValidationApiError([field_error(f, "required") for f in FIELDS])

    errors = [field_error(f, reason) for f in FIELDS if (reason := id_reason(body, f))]
    if errors:
        raise ValidationApiError(errors)

    return ReassignBehaviorInput(body["playerId"], body["behaviorId"])
