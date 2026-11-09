"""Validación del body de POST /leagues/{id}/participants.

Devuelve los datos tipados o lanza un 400 invalidFields con todos los
campos que fallan, en el orden del schema (convenciones 6, 7 y 9).
"""

from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.helpers.ids import MAX_ID
from app.services.field_validation import (
    FieldErrors,
    MemberInput,
    field_error,
    is_int,
    is_readable,
    members_errors,
    to_members,
)


@dataclass(frozen=True)
class JoinLeagueInput:
    password: str | None  # None si la liga es pública
    members: list[MemberInput]
    coach_behavior_id: int | None  # None: el equipo no tiene DT
    

def _password_errors(body: dict, private: bool) -> FieldErrors:
    if not private:
        return []
    password = body.get("password")
    if password is None:
        return [field_error("password", "required")]
    if not isinstance(password, str):
        return [field_error("password", "invalidType")]
    # "" no es error de validación: lo resuelve el 403 invalidLeaguePassword
    return []


def _coach_errors(body: dict) -> FieldErrors:
    value = body.get("coachBehaviorId")
    if value is None:  # ausente o null: el equipo no tiene DT
        return []
    if not is_int(value):
        return [field_error("coachBehaviorId", "invalidType")]
    if not 1 <= value <= MAX_ID:
        return [field_error("coachBehaviorId", "outOfRange")]
    return []


def _unreadable_body_errors(private: bool) -> FieldErrors:
    """Convención 9: cada campo requerido como `required`, en el orden del schema."""
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

    if not is_readable(body):
        raise ValidationApiError(_unreadable_body_errors(private))

    errors = [
        *_password_errors(body, private),
        *members_errors(body),
        *_coach_errors(body),
    ]
    if errors:
        raise ValidationApiError(errors)

    return JoinLeagueInput(
        password=body["password"] if private else None,
        members=to_members(body["members"]),
        coach_behavior_id=body.get("coachBehaviorId"),
    )