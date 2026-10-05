from dataclasses import dataclass
from typing import Any

from app.errors import ApiError

INVALID_JSON = object()  # sentinel: el body no se pudo parsear

MAX_NAME_LEN = 20
MIN_STAT, MAX_STAT = 20, 100
EXPECTED_SUM = 300
STATS = ("power", "agility", "control", "strength", "speed")


@dataclass(frozen=True)
class CreatePlayerInput:
    name: str
    power: int
    agility: int
    control: int
    strength: int
    speed: int


def _bad(code: str, message: str) -> ApiError:
    return ApiError(400, code, message)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_create_player(body: Any) -> CreatePlayerInput:
    if body is INVALID_JSON or (body is not None and not isinstance(body, dict)):
        raise _bad("invalidFieldType", "El body debe ser un objeto JSON válido.")

    body = body or {}

    # Validación de tipos (invalidFieldType)
    if "name" in body and not isinstance(body["name"], str):
        raise _bad("invalidFieldType", "`name` debe ser un string.")

    for stat in STATS:
        if stat in body and not _is_int(body[stat]):
            raise _bad("invalidFieldType", f"`{stat}` debe ser un número entero.")

    #  Formulario incompleto (incompleteForm)
    if "name" not in body:
        raise _bad("incompleteForm", "Falta `name`.")
    if body["name"].strip() == "":
        raise _bad("incompleteForm", "`name` no puede estar vacío.")

    for stat in STATS:
        if stat not in body:
            raise _bad("incompleteForm", f"Falta `{stat}`.")

    # Límites y rangos
    name = body["name"].strip()
    if len(name) > MAX_NAME_LEN:
        raise _bad("nameTooLong", f"`name` no puede superar {MAX_NAME_LEN} caracteres.")

    for stat in STATS:
        val = body[stat]
        if not (MIN_STAT <= val <= MAX_STAT):
            raise _bad("statOutOfRange", f"`{stat}` debe estar entre {MIN_STAT} y {MAX_STAT}.")

    # Suma de stats
    total_sum = sum(body[stat] for stat in STATS)
    if total_sum != EXPECTED_SUM:
        raise _bad(
            "statSumMismatch", f"La suma de las estadísticas debe ser exactamente {EXPECTED_SUM}."
        )

    return CreatePlayerInput(
        name=name,
        power=body["power"],
        agility=body["agility"],
        control=body["control"],
        strength=body["strength"],
        speed=body["speed"],
    )
