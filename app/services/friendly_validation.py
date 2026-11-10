from dataclasses import dataclass
from typing import Any

from app.errors import ValidationApiError
from app.services.field_validation import (
    MemberInput,
    all_required,
    field_error,
    is_readable,
    members_errors,
    str_reason,
    to_members,
)
from app.services.league_validation import MAX_NAME_LEN

REQUIRED = ("name", "members")


@dataclass(frozen=True)
class CreateFriendlyInput:
    name: str
    members: list[MemberInput]


@dataclass(frozen=True)
class JoinFriendlyInput:
    members: list[MemberInput]


def parse_create_friendly(body: Any) -> CreateFriendlyInput:
    """Valida el body de POST /friendlies (todos los campos que fallan, convención 6).

    Raises:
        ValidationApiError 400: invalidFields con todos los campos que fallan.
    """
    if not is_readable(body):
        raise ValidationApiError(all_required(REQUIRED))

    name_reason = str_reason(body, "name", MAX_NAME_LEN)
    errors = [field_error("name", name_reason)] if name_reason else []
    errors += members_errors(body)
    if errors:
        raise ValidationApiError(errors)

    return CreateFriendlyInput(name=body["name"], members=to_members(body["members"]))


def parse_join_friendly(body: Any) -> JoinFriendlyInput:
    """Valida el body de POST /friendlies/{id}/members. Un body ilegible cuenta
    como si faltara `members` (convención 9).

    Raises:
        ValidationApiError 400: invalidFields con todos los campos que fallan.
    """
    if not is_readable(body):
        raise ValidationApiError(all_required(("members",)))

    errors = members_errors(body)
    if errors:
        raise ValidationApiError(errors)

    return JoinFriendlyInput(members=to_members(body["members"]))