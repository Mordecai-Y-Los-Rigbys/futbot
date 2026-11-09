from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.services.field_validation import (
    FieldErrors,
    MemberInput,
    all_required,
    bool_reason,
    field_error,
    int_reason,
    is_readable,
    members_errors,
    str_reason,
    to_members,
)

MIN_PARTICIPANTS = 3
MAX_NAME_LEN = 20
MAX_PASSWORD_LEN = 72
MIN_DURATION, MAX_DURATION = 1, 10

REQUIRED = ("name", "minParticipants", "maxParticipants", "matchDuration", "private", "members")


@dataclass(frozen=True)
class CreateLeagueInput:
    name: str
    min_participants: int
    max_participants: int
    match_duration: int
    private: bool
    password: str | None
    members: list[MemberInput]


def _password_reason(body: dict) -> str | None:
    """Solo se evalúa si `private` es true (convención 7)."""
    if body.get("private") is not True:
        return None
    password = body.get("password")
    if password is None or password == "":
        return "required"
    if not isinstance(password, str):
        return "invalidType"
    if len(password) > MAX_PASSWORD_LEN:
        return "tooLong"
    return None


def _participants_errors(body: dict) -> FieldErrors:
    min_reason = int_reason(body, "minParticipants", MIN_PARTICIPANTS)
    max_reason = int_reason(body, "maxParticipants")
    if not min_reason and not max_reason and body["maxParticipants"] < body["minParticipants"]:
        max_reason = "lessThanMin"
    return [
        field_error(f, r)
        for f, r in (("minParticipants", min_reason), ("maxParticipants", max_reason))
        if r
    ]


def parse_create_league(body: Any) -> CreateLeagueInput:
    """Valida el body de POST /leagues y devuelve los datos de la liga.

    Informa todos los campos que fallan, en el orden del schema (convención 6).
    `password` solo cuenta si la liga es privada.

    Raises:
        ValidationApiError 400: invalidFields con todos los campos que fallan.
    """

    if not is_readable(body):
        raise ValidationApiError(all_required(REQUIRED))

    name_reason = str_reason(body, "name", MAX_NAME_LEN)
    errors = [field_error("name", name_reason)] if name_reason else []
    errors += _participants_errors(body)
    for field, reason in (
        ("matchDuration", int_reason(body, "matchDuration", MIN_DURATION, MAX_DURATION)),
        ("private", bool_reason(body, "private")),
        ("password", _password_reason(body)),
    ):
        if reason:
            errors.append(field_error(field, reason))
    errors += members_errors(body)

    if errors:
        raise ValidationApiError(errors)

    private = body["private"]
    return CreateLeagueInput(
        name=body["name"],
        min_participants=body["minParticipants"],
        max_participants=body["maxParticipants"],
        match_duration=body["matchDuration"],
        private=private,
        password=body["password"] if private else None,
        members=to_members(body["members"]),
    )