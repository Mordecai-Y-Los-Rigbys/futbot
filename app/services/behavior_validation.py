from typing import Any

from app.domain.behavior import BehaviorType
from app.errors import ValidationApiError
from app.repositories.behavior_abstract import CreateBehaviorData
from app.services.field_validation import field_error
from app.services.league_validation import INVALID_JSON

FIELDS = ("name", "code", "type")
MAX_NAME_LEN = 20
TYPES = {behavior_type.value for behavior_type in BehaviorType}


def parse_create_behavior(body: Any) -> CreateBehaviorData:
    """Valida el body y devuelve los datos para crear el behavior.

    Raises:
        ValidationApiError: 400 con todos los campos que fallan, en el orden del schema.
    """
    if body is INVALID_JSON or not isinstance(body, dict):
        raise ValidationApiError([field_error(field, "required") for field in FIELDS])
    body = _strip_name(body)

    reasons = {"name": _name_reason(body), "code": _string_reason(body, "code")}
    reasons["type"] = _type_reason(body)
    errors = [field_error(field, reasons[field]) for field in FIELDS if reasons[field]]
    if errors:
        raise ValidationApiError(errors)

    return CreateBehaviorData(name=body["name"], code=body["code"], type=BehaviorType(body["type"]))


def _strip_name(body: dict) -> dict:
    """Saca los espacios de los extremos del nombre, como en los otros nombres del sistema.

    Se recorta una sola vez: el largo, el nombre repetido y lo que se guarda usan este valor.
    """
    if isinstance(body.get("name"), str):
        return {**body, "name": body["name"].strip()}
    return body


def _string_reason(body: dict, key: str) -> str | None:
    if key not in body:
        return "required"
    if not isinstance(body[key], str):  # incluye null
        return "invalidType"
    return None


def _name_reason(body: dict) -> str | None:
    reason = _string_reason(body, "name")
    if reason:
        return reason
    if not body["name"]:
        return "required"
    if len(body["name"]) > MAX_NAME_LEN:
        return "tooLong"
    return None


def _type_reason(body: dict) -> str | None:
    reason = _string_reason(body, "type")
    if reason:
        return reason
    if body["type"] not in TYPES:
        return "invalidValue"
    return None
