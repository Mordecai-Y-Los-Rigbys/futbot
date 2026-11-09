from typing import Any

from app.domain.behavior import BehaviorType
from app.errors import ValidationApiError
from app.repositories.behavior_abstract import CreateBehaviorData, UpdateBehaviorData
from app.services.field_validation import field_error
from app.services.league_validation import INVALID_JSON

CREATE_FIELDS = ("name", "code", "type")
UPDATE_FIELDS = ("name", "code")  # el tipo no se puede cambiar
MAX_NAME_LEN = 20
TYPES = {behavior_type.value for behavior_type in BehaviorType}


def parse_create_behavior(body: Any) -> CreateBehaviorData:
    """Valida el body de POST /behaviors y devuelve los datos para crear el behavior.

    Raises:
        ValidationApiError: 400 con todos los campos que fallan, en el orden del schema.
    """
    _ensure_object(body, CREATE_FIELDS)
    body = _strip_name(body)
    _raise_errors(
        CREATE_FIELDS,
        {
            "name": _name_reason(body),
            "code": _string_reason(body, "code"),
            "type": _type_reason(body),
        },
    )
    return CreateBehaviorData(name=body["name"], code=body["code"], type=BehaviorType(body["type"]))


def parse_update_behavior(body: Any) -> UpdateBehaviorData:
    """Valida el body de PUT /behaviors/{id}. Si viene `type`, se ignora.

    Raises:
        ValidationApiError: 400 con todos los campos que fallan, en el orden del schema.
    """
    _ensure_object(body, UPDATE_FIELDS)
    _raise_errors(UPDATE_FIELDS, {"name": _name_reason(body), "code": _string_reason(body, "code")})
    return UpdateBehaviorData(name=body["name"], code=body["code"])


def _ensure_object(body: Any, fields: tuple[str, ...]) -> None:
    """Un body ilegible o que no es un objeto: todos los campos `required` (convención 9)."""
    if body is INVALID_JSON or not isinstance(body, dict):
        raise ValidationApiError([field_error(field, "required") for field in fields])


def _raise_errors(fields: tuple[str, ...], reasons: dict[str, str | None]) -> None:
    errors = [field_error(field, reasons[field]) for field in fields if reasons[field]]
    if errors:
        raise ValidationApiError(errors)


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
