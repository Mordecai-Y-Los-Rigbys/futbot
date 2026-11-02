"""Validación del body de POST /leagues/{id}/participants.

Devuelve los datos tipados o lanza un 400 invalidFields con todos los
campos que fallan, en el orden del schema (convenciones 6, 7 y 9).
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.helpers.ids import MAX_ID
from app.services.league_validation import INVALID_JSON, REQUIRED_ROLES, TEAM_SIZE, MemberInput
from app.services.field_validation import field_error, id_reason, is_int


@dataclass(frozen=True)
class JoinLeagueInput:
    password: str | None  # None si la liga es pública (se ignora, convención 7)
    members: list[MemberInput]
    coach_behavior_id: int | None  # None: el equipo no tiene DT


def _role_reason(member: dict) -> str | None:
    # Un string que no es un rol válido NO es error de campo: es invalidTeam (6.h).
    if "role" not in member:
        return "required"
    if not isinstance(member["role"], str):
        return "invalidType"
    return None


def _passwordfield_errors(body: dict, private: bool) -> list[dict[str, str]]:
    if not private:
        return []  # liga pública: se ignora por completo, incluido el tipo
    password = body.get("password")
    if password is None:  # falta o es null
        return [field_error("password", "required")]
    if not isinstance(password, str):
        return [field_error("password", "invalidType")]
    # "" no es error de validación: lo resuelve el 403 invalidLeaguePassword
    return []


def _memberfield_errors(index: int, member: Any) -> list[dict[str, str]]:
    if not isinstance(member, dict):
        return [field_error(f"members[{index}]", "invalidType")]
    reasons = (
        ("playerId", id_reason (member, "playerId")),
        ("role", _role_reason(member)),
        ("behaviorId", id_reason (member, "behaviorId")),
    )
    return [field_error(f"members[{index}].{key}", reason) for key, reason in reasons if reason]


def _is_valid_team(members: list[dict]) -> bool:
    return (
        len(members) == TEAM_SIZE
        and dict(Counter(m["role"] for m in members)) == REQUIRED_ROLES
        and len({m["playerId"] for m in members}) == TEAM_SIZE
    )


def _membersfield_errors(body: dict) -> list[dict[str, str]]:
    if "members" not in body:
        return [field_error("members", "required")]
    members = body["members"]
    if not isinstance(members, list):  # incluye null
        return [field_error("members", "invalidType")]

    errors = [e for i, m in enumerate(members) for e in _memberfield_errors(i, m)]
    # invalidTeam cruza campos: solo si ningún elemento tuvo errores (6.f)
    if not errors and not _is_valid_team(members):
        errors.append(field_error("members", "invalidTeam"))
    return errors


def _coachfield_errors(body: dict) -> list[dict[str, str]]:
    value = body.get("coachBehaviorId")
    if value is None:  # ausente o null: el equipo no tiene DT
        return []
    if not is_int(value):
        return [field_error("coachBehaviorId", "invalidType")]
    if not 1 <= value <= MAX_ID:
        return [field_error("coachBehaviorId", "outOfRange")]
    return []


def _unreadable_bodyfield_errors(private: bool) -> list[dict[str, str]]:
    """Convención 9: cada campo requerido como `required`, en el orden del schema.
    `coachBehaviorId` es opcional, así que no aparece."""
    fields = (["password"] if private else []) + ["members"]
    return [field_error(f, "required") for f in fields]


def parse_join_league(body: Any, private: bool) -> JoinLeagueInput:
    """Valida el body de una inscripción y devuelve los datos ya tipados.

    Args:
        body: JSON del request sin validar (None si vino vacío, INVALID_JSON
            si no se pudo parsear).
        private: si la liga es privada; define si `password` se evalúa.

    Raises:
        ValidationApiError: 400 `invalidFields` con todos los campos que fallan.
    """

    if body is INVALID_JSON or not isinstance(body, dict):  # incluye None, arrays, etc.
        raise ValidationApiError(_unreadable_bodyfield_errors(private))

    errors = [
        *_passwordfield_errors(body, private),
        *_membersfield_errors(body),
        *_coachfield_errors(body),
    ]
    if errors:
        raise ValidationApiError(errors)

    return JoinLeagueInput(
        password=body["password"] if private else None,
        members=[MemberInput(m["playerId"], m["behaviorId"], m["role"]) for m in body["members"]],
        coach_behavior_id=body.get("coachBehaviorId"),
    )
