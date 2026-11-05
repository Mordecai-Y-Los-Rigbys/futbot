from typing import Any, Dict, List
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.auth import MAX_EMAIL_LENGTH

REGISTER_FIELDS = ("username", "email", "password", "clubName", "avatar")

LOGIN_FIELDS = ("email", "password")

# Tipos de error de Pydantic/FastAPI que indican que el body entero es ilegible
UNREADABLE_BODY_TYPES = {"json_invalid", "model_attributes_type"}


class ApiError(Exception):
    """Error con la forma del contrato: { "code": str | None, "message": str }."""

    def __init__(self, status_code: int, code: str | None, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"code": self.code, "message": self.message},
        )


class ValidationApiError(ApiError):
    """400 de validación del contrato (convención 6).

    `code` fijo `invalidFields` y `errors` con un `{field, reason}` por cada
    campo que falló, en el orden del schema del request.
    """

    MESSAGE = "Revisá los campos marcados."

    def __init__(self, errors: List[Dict[str, str]]) -> None:
        super().__init__(400, "invalidFields", self.MESSAGE)
        self.errors = errors

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"code": self.code, "message": self.message, "errors": self.errors},
        )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return exc.to_response()


# ------------------------------------------------------------------
# Register
# ------------------------------------------------------------------


def determine_rejection_reason(error_detail: Dict[str, Any], field: str) -> str:
    err_type: str = error_detail.get("type", "")
    value = error_detail.get("input")

    # Faltante o vacío (string_too_short: min_length=1)
    if err_type in ("missing", "string_too_short"):
        return "required"

    # Demasiado largo
    if err_type == "string_too_long":
        return "tooLong"

    # Entero fuera de rango (avatar)
    if err_type in ("greater_than_equal", "less_than_equal"):
        return "outOfRange"

    # Email: EmailStr informa vacío, largo excesivo y formato inválido con el mismo
    # error (value_error), así que se distinguen por el valor. El orden importa.
    if field == "email" and isinstance(value, str):
        if value == "":
            return "required"
        if len(value) > MAX_EMAIL_LENGTH:
            return "tooLong"
        return "invalidEmail"

    # Todo lo demás es un tipo inválido (string_type, int_type, etc.)
    return "invalidType"


def _register_field(error_detail: Dict[str, Any]) -> str | None:
    """Devuelve el campo conocido del body, o None si el error es del body entero."""
    loc = tuple(error_detail.get("loc", ()))
    if len(loc) >= 2 and loc[0] == "body" and loc[1] in REGISTER_FIELDS:
        return loc[1]
    return None


def build_field_error(error_detail: Dict[str, Any]) -> Dict[str, str] | None:
    field = _register_field(error_detail)
    if field is None:
        return None
    return {"field": field, "reason": determine_rejection_reason(error_detail, field)}


def handle_register_validation_error(exc: RequestValidationError) -> JSONResponse:
    by_field: Dict[str, Dict[str, str]] = {}
    for err in exc.errors():
        fe = build_field_error(err)
        if fe is not None and fe["field"] not in by_field:
            by_field[fe["field"]] = fe

    field_errors = sorted(by_field.values(), key=lambda fe: REGISTER_FIELDS.index(fe["field"]))
    if not field_errors:
        # Body ilegible (JSON roto, vacío, array): se reportan los cinco campos
        field_errors = [{"field": f, "reason": "required"} for f in REGISTER_FIELDS]

    return ValidationApiError(field_errors).to_response()


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------


def handle_login_validation_error(exc: RequestValidationError) -> JSONResponse:
    """Traduce los errores de /auth/log-in al formato invalidFields del contrato."""
    by_field: Dict[str, Dict[str, str]] = {}
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        if len(loc) >= 2 and loc[0] == "body" and loc[1] in LOGIN_FIELDS and loc[1] not in by_field:
            reason = determine_rejection_reason(err, loc[1])
            if reason == "tooLong":
                # Login no define tooLong (contrato): un email demasiado largo no es un email válido
                reason = "invalidEmail"
            by_field[loc[1]] = {"field": loc[1], "reason": reason}

    field_errors = sorted(by_field.values(), key=lambda fe: LOGIN_FIELDS.index(fe["field"]))
    if not field_errors:
        # Body ilegible (JSON roto, vacío, array): faltan ambos campos
        field_errors = [{"field": f, "reason": "required"} for f in LOGIN_FIELDS]

    return ValidationApiError(field_errors).to_response()


# ------------------------------------------------------------------
# Genérico y dispatcher
# ------------------------------------------------------------------


def _field_path(loc: tuple) -> str:
    """("body", "members", 0, "playerId") -> "members[0].playerId"."""
    path = ""
    for part in loc[1:]:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path


def handle_generic_validation_error(exc: RequestValidationError) -> JSONResponse:
    """Respaldo para endpoints con modelos de Pydantic sin handler propio."""
    by_field: Dict[str, Dict[str, str]] = {}
    for err in exc.errors():
        if err.get("type") in UNREADABLE_BODY_TYPES:
            continue
        field = _field_path(tuple(err.get("loc", ())))
        if field and field not in by_field:
            by_field[field] = {"field": field, "reason": determine_rejection_reason(err, field)}

    if not by_field:
        # Body ilegible: sin el schema del endpoint no se sabe qué campos faltan
        by_field["body"] = {"field": "body", "reason": "required"}
    return ValidationApiError(list(by_field.values())).to_response()


VALIDATION_HANDLERS = {
    "/auth/register": handle_register_validation_error,
    "/auth/log-in": handle_login_validation_error,
}


def _route_path(request: Request) -> str:
    # La ruta declarada (con prefijo de router, sin root_path); si no, la URL cruda
    route = request.scope.get("route")
    return (getattr(route, "path", None) or request.url.path).rstrip("/")


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    path = _route_path(request)
    handler = next(
        (h for suffix, h in VALIDATION_HANDLERS.items() if path.endswith(suffix)),
        handle_generic_validation_error,
    )
    return handler(exc)
