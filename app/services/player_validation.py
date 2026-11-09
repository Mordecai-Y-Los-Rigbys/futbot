from typing import Any

from app.errors import ValidationApiError
from app.repositories.player_abstract import CreatePlayerData
from app.services.field_validation import (
    all_required,
    field_error,
    int_reason,
    is_readable,
    str_reason,
)

MAX_NAME_LEN = 20
MIN_STAT, MAX_STAT = 20, 100
EXPECTED_SUM = 300
STATS = ("power", "agility", "control", "strength", "speed")


def parse_create_player(body: Any) -> CreatePlayerData:
    """Valida el body de POST /players y devuelve los datos para crear el jugador.

    Informa todos los campos que fallan, en el orden del schema (convención 6).
    `stats` / `invalidSum` solo se evalúa si las cinco stats son válidas. El
    nombre se guarda sin espacios al principio ni al final.

    Raises:
        ValidationApiError 400: invalidFields con todos los campos que fallan.
    """

    if not is_readable(body):
        raise ValidationApiError(all_required(("name", *STATS)))

    reasons = {"name": str_reason(body, "name", MAX_NAME_LEN, strip=True)}
    for stat in STATS:
        reasons[stat] = int_reason(body, stat, MIN_STAT, MAX_STAT)

    errors = [field_error(f, r) for f, r in reasons.items() if r]
    stats_ok = not any(reasons[s] for s in STATS)
    if stats_ok and sum(body[s] for s in STATS) != EXPECTED_SUM:
        errors.append(field_error("stats", "invalidSum"))

    if errors:
        raise ValidationApiError(errors)

    return CreatePlayerData(
        name=body["name"].strip(),
        power=body["power"],
        agility=body["agility"],
        control=body["control"],
        strength=body["strength"],
        speed=body["speed"],
    )