from dataclasses import dataclass
from typing import Any

from app.helpers.ids import MAX_ID
from app.services.league_validation import (
    INVALID_JSON,
    MAX_NAME_LEN,
    MEMBER_KEYS,
    MemberInput,
    _bad,
    _check_team,
    _is_id,
)

REQUIRED = ("name", "members")


@dataclass(frozen=True)
class CreateFriendlyInput:
    name: str
    members: list[MemberInput]


def _check_types(body: dict) -> None:
    """invalidFieldType: tipos incorrectos o IDs fuera de rango."""

    def fail(msg: str):
        raise _bad("invalidFieldType", msg)

    if "name" in body and not isinstance(body["name"], str):
        fail("`name` debe ser un string.")
    if "members" in body:
        if not isinstance(body["members"], list):
            fail("`members` debe ser un array.")
        for m in body["members"]:
            if not isinstance(m, dict):
                fail("Cada elemento de `members` debe ser un objeto.")
            for f in ("playerId", "behaviorId"):
                if f in m and not _is_id(m[f]):
                    fail(f"`{f}` debe ser un entero entre 1 y {MAX_ID}.")
            if "role" in m and not isinstance(m["role"], str):
                fail("`role` debe ser un string.")


def parse_create_friendly(body: Any) -> CreateFriendlyInput:
    """Todos los 400, en orden: invalidFieldType > incompleteForm >
    nameTooLong > invalidTeam."""
    if body is INVALID_JSON or (body is not None and not isinstance(body, dict)):
        raise _bad("invalidFieldType", "El body debe ser un objeto JSON válido.")
    body = body or {}

    _check_types(body)

    missing = [f for f in REQUIRED if f not in body]
    if missing:
        raise _bad("incompleteForm", f"Falta `{missing[0]}`.")
    if body["name"] == "":
        raise _bad("incompleteForm", "`name` no puede estar vacío.")
    for m in body["members"]:
        for k in MEMBER_KEYS:
            if k not in m:
                raise _bad("incompleteForm", f"Cada elemento de `members` necesita `{k}`.")

    if len(body["name"]) > MAX_NAME_LEN:
        raise _bad("nameTooLong", f"`name` no puede superar {MAX_NAME_LEN} caracteres.")

    _check_team(body["members"])

    return CreateFriendlyInput(
        name=body["name"],
        members=[MemberInput(m["playerId"], m["behaviorId"], m["role"]) for m in body["members"]],
    )


@dataclass(frozen=True)
class JoinFriendlyInput:
    members: list[MemberInput]


def _check_members_types(body: dict) -> None:
    """invalidFieldType para `members` (sin mirar `name`, que acá se ignora)."""

    def fail(msg: str):
        raise _bad("invalidFieldType", msg)

    if "members" in body:
        if not isinstance(body["members"], list):
            fail("`members` debe ser un array.")
        for m in body["members"]:
            if not isinstance(m, dict):
                fail("Cada elemento de `members` debe ser un objeto.")
            for f in ("playerId", "behaviorId"):
                if f in m and not _is_id(m[f]):
                    fail(f"`{f}` debe ser un entero entre 1 y {MAX_ID}.")
            if "role" in m and not isinstance(m["role"], str):
                fail("`role` debe ser un string.")


def parse_join_friendly(body: Any) -> JoinFriendlyInput:
    """Todos los 400, en orden: invalidFieldType > incompleteForm > invalidTeam.
    Un body ilegible, vacío o que no es un objeto cuenta como si faltara
    `members` (convención 9) y se evalúa antes que cualquier regla de campo."""
    if body is None or body is INVALID_JSON or not isinstance(body, dict):
        raise _bad("incompleteForm", "Falta `members`.")

    _check_members_types(body)

    if "members" not in body:
        raise _bad("incompleteForm", "Falta `members`.")
    for m in body["members"]:
        for k in MEMBER_KEYS:
            if k not in m:
                raise _bad("incompleteForm", f"Cada elemento de `members` necesita `{k}`.")

    _check_team(body["members"])

    return JoinFriendlyInput(
        members=[MemberInput(m["playerId"], m["behaviorId"], m["role"]) for m in body["members"]]
    )
