"""Validación del body de POST /leagues/{id}/participants (convenciones 6, 7 y 9).

A diferencia de las validaciones viejas (league_validation, friendly_validation),
acá NO se corta en el primer error: se juntan todos los campos que fallan, con
un único `reason` por campo y en el orden del schema (`password`, `members`,
`coachBehaviorId`), y se lanzan juntos como 400 `invalidFields`.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.helpers.ids import MAX_ID
from app.services.league_validation import INVALID_JSON, REQUIRED_ROLES, TEAM_SIZE, MemberInput


@dataclass(frozen=True)
class JoinLeagueInput:
    password: str | None  # None si la liga es pública (se ignora, convención 7)
    members: list[MemberInput]
    coach_behavior_id: int | None  # None: el equipo no tiene DT


def _error(field: str, reason: str) -> dict[str, str]:
    return {"field": field, "reason": reason}


def _is_int(value: Any) -> bool:
    # bool es subclase de int en Python, pero `true` no es un entero JSON.
    # 1.0 llega como float: tampoco es un entero.
    return isinstance(value, int) and not isinstance(value, bool)


def _id_reason(container: dict, key: str) -> str | None:
    """required > invalidType > outOfRange (convención 6.e)."""
    if key not in container:
        return "required"
    value = container[key]
    if not _is_int(value):  # incluye null
        return "invalidType"
    if not 1 <= value <= MAX_ID:
        return "outOfRange"
    return None


def _role_reason(member: dict) -> str | None:
    # Un string que no es un rol válido NO es error de campo: es invalidTeam (6.h).
    if "role" not in member:
        return "required"
    if not isinstance(member["role"], str):
        return "invalidType"
    return None


def _password_errors(body: dict, private: bool) -> list[dict[str, str]]:
    if not private:
        return []  # liga pública: se ignora por completo, incluido el tipo
    password = body.get("password")
    if password is None:  # falta o es null
        return [_error("password", "required")]
    if not isinstance(password, str):
        return [_error("password", "invalidType")]
    # "" no es error de validación: lo resuelve el 403 invalidLeaguePassword
    return []


def _member_errors(index: int, member: Any) -> list[dict[str, str]]:
    if not isinstance(member, dict):
        return [_error(f"members[{index}]", "invalidType")]
    reasons = (
        ("playerId", _id_reason(member, "playerId")),
        ("role", _role_reason(member)),
        ("behaviorId", _id_reason(member, "behaviorId")),
    )
    return [_error(f"members[{index}].{key}", reason) for key, reason in reasons if reason]


def _is_valid_team(members: list[dict]) -> bool:
    return (
        len(members) == TEAM_SIZE
        and dict(Counter(m["role"] for m in members)) == REQUIRED_ROLES
        and len({m["playerId"] for m in members}) == TEAM_SIZE
    )


def _members_errors(body: dict) -> list[dict[str, str]]:
    if "members" not in body:
        return [_error("members", "required")]
    members = body["members"]
    if not isinstance(members, list):  # incluye null
        return [_error("members", "invalidType")]

    errors = [e for i, m in enumerate(members) for e in _member_errors(i, m)]
    # invalidTeam cruza campos: solo si ningún elemento tuvo errores (6.f)
    if not errors and not _is_valid_team(members):
        errors.append(_error("members", "invalidTeam"))
    return errors


def _coach_errors(body: dict) -> list[dict[str, str]]:
    value = body.get("coachBehaviorId")
    if value is None:  # ausente o null: el equipo no tiene DT
        return []
    if not _is_int(value):
        return [_error("coachBehaviorId", "invalidType")]
    if not 1 <= value <= MAX_ID:
        return [_error("coachBehaviorId", "outOfRange")]
    return []


def _unreadable_body_errors(private: bool) -> list[dict[str, str]]:
    """Convención 9: cada campo requerido como `required`, en el orden del schema.
    `coachBehaviorId` es opcional, así que no aparece."""
    fields = (["password"] if private else []) + ["members"]
    return [_error(f, "required") for f in fields]


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
        raise ValidationApiError(_unreadable_body_errors(private))

    errors = [
        *_password_errors(body, private),
        *_members_errors(body),
        *_coach_errors(body),
    ]
    if errors:
        raise ValidationApiError(errors)

    return JoinLeagueInput(
        password=body["password"] if private else None,
        members=[MemberInput(m["playerId"], m["behaviorId"], m["role"]) for m in body["members"]],
        coach_behavior_id=body.get("coachBehaviorId"),
    )
