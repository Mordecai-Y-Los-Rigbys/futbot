from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.services.field_validation import field_error, id_reason, string_reason
from app.services.league_validation import INVALID_JSON

CLUBS = ("club1", "club2")
ROLES = ("forward", "midfield", "defense")
LINEUP_SIZE = len(CLUBS) * len(ROLES)
REQUIRED_SLOTS = {(club, role): 1 for club in CLUBS for role in ROLES}


@dataclass(frozen=True)
class LineupMemberInput:
    player_id: int
    club: str
    role: str
    behavior_id: int


def _member_errors(index: int, member: Any) -> list[dict[str, str]]:
    if not isinstance(member, dict):
        return [field_error(f"members[{index}]", "invalidType")]
    reasons = (
        ("playerId", id_reason(member, "playerId")),
        ("club", string_reason(member, "club")),
        ("role", string_reason(member, "role")),
        ("behaviorId", id_reason(member, "behaviorId")),
    )
    return [field_error(f"members[{index}].{key}", reason) for key, reason in reasons if reason]


def _is_valid_lineup(members: list[dict]) -> bool:
    # Un club o un rol fuera del enum no ocupa ningún lugar: también es invalidTeam.
    return (
        len(members) == LINEUP_SIZE
        and len({m["playerId"] for m in members}) == LINEUP_SIZE
        and dict(Counter((m["club"], m["role"]) for m in members)) == REQUIRED_SLOTS
    )


def parse_behavior_test(body: Any) -> list[LineupMemberInput]:
    """Valida el body de POST /behaviors/{id}/test-connections.

    Raises:
        ValidationApiError: 400 `invalidFields` con todos los campos que fallan.
    """
    # Body ilegible, vacío o que no es un objeto: falta `members` (convención 9).
    if body is INVALID_JSON or not isinstance(body, dict) or "members" not in body:
        raise ValidationApiError([field_error("members", "required")])
    members = body["members"]
    if not isinstance(members, list):  # incluye null
        raise ValidationApiError([field_error("members", "invalidType")])

    errors = [e for i, m in enumerate(members) for e in _member_errors(i, m)]
    if not errors and not _is_valid_lineup(members):
        errors.append(field_error("members", "invalidTeam"))
    if errors:
        raise ValidationApiError(errors)

    return [
        LineupMemberInput(m["playerId"], m["club"], m["role"], m["behaviorId"]) for m in members
    ]
