from typing import Any, Dict, List
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.auth import (
    LogInBadRequest,
    RegisterUserBadRequest,
    RegisterUserFieldError,
    LogInFieldError
)

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


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return exc.to_response()


def is_unreadable_body(errors: List[Dict[str, Any]]) -> bool:
    """JSON roto, body vacío o body que no es un objeto: el error es del body entero."""
    return any(
        err.get("type") in UNREADABLE_BODY_TYPES or tuple(err.get("loc", ())) == ("body",)
        for err in errors
    )


# ------------------------------------------------------------------
# Register
# ------------------------------------------------------------------


def determine_rejection_reason(error_detail: Dict[str, Any]) -> str:
    err_type: str = error_detail.get("type", "")

    if err_type in ("missing", "string_too_short"):
        return "required"
    
    if err_type == "string_too_long":
        return "tooLong"
    
    if err_type in ("greater_than_equal", "less_than_equal"):
        return "outOfRange"
    
    if err_type == "value_error":
        return "invalidEmail"
    
    return "invalidType"


def _register_field(error_detail: Dict[str, Any]) -> str | None:
    """Devuelve el campo conocido del body, o None si el error es del body entero."""
    loc = tuple(error_detail.get("loc", ()))
    if len(loc) >= 2 and loc[0] == "body" and loc[1] in REGISTER_FIELDS:
        return loc[1]
    return None


def build_field_error(error_detail: Dict[str, Any]) -> RegisterUserFieldError | None:
    field = _register_field(error_detail)
    if field is None:
        return None
    return RegisterUserFieldError(
        field=field, reason=determine_rejection_reason(error_detail)
    )


def handle_register_validation_error(exc: RequestValidationError) -> JSONResponse:
    by_field: dict[str, RegisterUserFieldError] = {}
    for err in exc.errors():
        fe = build_field_error(err)
        if fe is not None and fe.field not in by_field:
            by_field[fe.field] = fe

    field_errors = sorted(by_field.values(), key=lambda fe: REGISTER_FIELDS.index(fe.field))
    if not field_errors:
        # Body ilegible (JSON roto, vacío, array): se reportan los cinco campos
        field_errors = [RegisterUserFieldError(field=f, reason="required") for f in REGISTER_FIELDS]

    payload = RegisterUserBadRequest(message="Revisá los campos marcados.", errors=field_errors)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(by_alias=True),
    )


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------


def handle_login_validation_error(exc: RequestValidationError) -> JSONResponse:
    """Traduce los errores de /auth/log-in al formato invalidFields del contrato."""
    by_field: dict[str, LogInFieldError] = {}
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        if len(loc) >= 2 and loc[0] == "body" and loc[1] in LOGIN_FIELDS and loc[1] not in by_field:
            by_field[loc[1]] = LogInFieldError(
                field=loc[1], reason=determine_rejection_reason(err)
            )

    field_errors = sorted(by_field.values(), key=lambda fe: LOGIN_FIELDS.index(fe.field))
    if not field_errors:
        # Body ilegible (JSON roto, vacío, array): faltan ambos campos
        field_errors = [LogInFieldError(field=f, reason="required") for f in LOGIN_FIELDS]

    payload = LogInBadRequest(message="Revisá los campos marcados.", errors=field_errors)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(),
    )


# ------------------------------------------------------------------
# Genérico y dispatcher
# ------------------------------------------------------------------


def handle_generic_validation_error(exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    only_missing = all(err.get("type") == "missing" for err in errors)

    if only_missing or is_unreadable_body(errors):
        code, message = "incompleteForm", "Completá todos los campos."
    else:
        code, message = "invalidFieldType", "Algún campo tiene un tipo inválido."

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"code": code, "message": message},
    )


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
