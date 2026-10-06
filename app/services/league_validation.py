from collections import Counter
from dataclasses import dataclass
from typing import Any, NoReturn

from app.errors import ApiError
from app.helpers.ids import MAX_ID


INVALID_JSON = object()  # sentinel: el body no se pudo parsear

MIN_PARTICIPANTS = 3
MAX_NAME_LEN = 20
MAX_PASSWORD_LEN = 72
MIN_DURATION, MAX_DURATION = 1, 10
REQUIRED_ROLES = {"forward": 1, "midfield": 1, "defense": 1, "substitute": 3}
TEAM_SIZE = 6

REQUIRED = ("name", "minParticipants", "maxParticipants", "matchDuration", "private", "members")
INT_FIELDS = ("minParticipants", "maxParticipants", "matchDuration")
MEMBER_KEYS = ("playerId", "role", "behaviorId")


@dataclass(frozen=True)
class MemberInput:
    player_id: int
    behavior_id: int
    role: str


@dataclass(frozen=True)
class CreateLeagueInput:
    name: str
    min_participants: int
    max_participants: int
    match_duration: int
    private: bool
    password: str | None  # None si la liga es pública (se ignora)
    members: list[MemberInput]


def _bad(code: str, message: str) -> ApiError:
    return ApiError(400, code, message)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_id(v: Any) -> bool:
    return _is_int(v) and 1 <= v <= MAX_ID


def _invalid_type(message: str) -> NoReturn:
    raise _bad("invalidFieldType", message)


def _check_member_types(member: Any) -> None:
    """invalidFieldType de un elemento de `members`."""
    if not isinstance(member, dict):
        _invalid_type("Cada elemento de `members` debe ser un objeto.")
    for field in ("playerId", "behaviorId"):
        if field in member and not _is_id(member[field]):
            _invalid_type(f"`{field}` debe ser un entero entre 1 y {MAX_ID}.")
    if "role" in member and not isinstance(member["role"], str):
        _invalid_type("`role` debe ser un string.")


def _check_members_types(body: dict) -> None:
    """invalidFieldType de `members`: un array de objetos con ids y rol válidos."""
    if "members" not in body:
        return
    if not isinstance(body["members"], list):
        _invalid_type("`members` debe ser un array.")
    for member in body["members"]:
        _check_member_types(member)


def _check_types(body: dict) -> None:
    """Regla (a): invalidFieldType. `password` solo se evalúa si private es true."""

    if "name" in body and not isinstance(body["name"], str):
        _invalid_type("`name` debe ser un string.")
    for f in INT_FIELDS:
        if f in body and (not _is_int(body[f]) or body[f] > MAX_ID):
            _invalid_type(f"`{f}` debe ser un entero.")
    if "private" in body and not isinstance(body["private"], bool):
        _invalid_type("`private` debe ser un booleano.")
    if body.get("private") is True:
        pw = body.get("password")
        if pw is not None and not isinstance(pw, str):
            _invalid_type("`password` debe ser un string.")

    _check_members_types(body)


def _check_team(members: list[dict]) -> None:
    """Regla (d): invalidTeam, siempre la última de los 400."""
    if len(members) != TEAM_SIZE:
        raise _bad("invalidTeam", f"`members` debe tener exactamente {TEAM_SIZE} elementos.")
    if dict(Counter(m["role"] for m in members)) != REQUIRED_ROLES:
        raise _bad(
            "invalidTeam",
            "`members` debe tener un forward, un midfield, un defense y tres substitute.",
        )
    ids = [m["playerId"] for m in members]
    if len(set(ids)) != len(ids):
        raise _bad("invalidTeam", "`playerId` no puede repetirse en el equipo.")


def parse_create_league(body: Any) -> CreateLeagueInput:
    """Valida el body de POST /leagues y devuelve los datos de la liga.

    Las reglas se evalúan en este orden y se lanza solo la primera que falla
    (convención 6): invalidFieldType > incompleteForm > nameTooLong >
    minParticipantsTooLow > maxLessThanMin > matchDurationOutOfRange >
    passwordTooLong > invalidTeam. `password` solo cuenta si la liga es privada.

    Raises:
        ApiError 400: con el código de la primera regla que falla.
    """

    if body is INVALID_JSON or (body is not None and not isinstance(body, dict)):
        raise _bad("invalidFieldType", "El body debe ser un objeto JSON válido.")
    body = body or {}

    # (a) tipos
    _check_types(body)

    # (b) formulario incompleto
    missing = [f for f in REQUIRED if f not in body]
    if missing:
        raise _bad("incompleteForm", f"Falta `{missing[0]}`.")
    private = body["private"]
    if private and not body.get("password"):  # ausente, null o ""
        raise _bad("incompleteForm", "`password` es obligatorio en ligas privadas.")
    if body["name"] == "":
        raise _bad("incompleteForm", "`name` no puede estar vacío.")
    for m in body["members"]:
        for k in MEMBER_KEYS:
            if k not in m:
                raise _bad("incompleteForm", f"Cada elemento de `members` necesita `{k}`.")

    # (c) reglas de contenido, en el orden del enum del YAML
    if len(body["name"]) > MAX_NAME_LEN:
        raise _bad("nameTooLong", f"`name` no puede superar {MAX_NAME_LEN} caracteres.")
    if body["minParticipants"] < MIN_PARTICIPANTS:
        raise _bad(
            "minParticipantsTooLow",
            f"`minParticipants` debe ser al menos {MIN_PARTICIPANTS}.",
        )
    if body["maxParticipants"] < body["minParticipants"]:
        raise _bad("maxLessThanMin", "`maxParticipants` no puede ser menor que `minParticipants`.")
    if not MIN_DURATION <= body["matchDuration"] <= MAX_DURATION:
        raise _bad(
            "matchDurationOutOfRange",
            f"`matchDuration` debe estar entre {MIN_DURATION} y {MAX_DURATION}.",
        )
    if private and len(body["password"]) > MAX_PASSWORD_LEN:
        raise _bad("passwordTooLong", f"`password` no puede superar {MAX_PASSWORD_LEN} caracteres.")

    # (d) equipo
    _check_team(body["members"])

    return CreateLeagueInput(
        name=body["name"],
        min_participants=body["minParticipants"],
        max_participants=body["maxParticipants"],
        match_duration=body["matchDuration"],
        private=private,
        password=body["password"] if private else None,
        members=[MemberInput(m["playerId"], m["behaviorId"], m["role"]) for m in body["members"]],
    )
