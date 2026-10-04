from typing import Any, Dict, List
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.auth import (
    LogInBadRequest,
    RegisterUserBadRequest,
    RegisterUserFieldError,
)

REGISTER_FIELDS = ("username", "email", "password", "clubName", "avatar")

# Tipos de error de Pydantic/FastAPI que indican que el body entero es ilegible
UNREADABLE_BODY_TYPES = {"json_invalid", "model_attributes_type"}


class ApiError(Exception):
    """Error con la forma del contrato: { "code": str | None, "message": str }."""

    def __init__(self, status_code: int, code: str | None, message: str):
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
        err.get("type") in UNREADABLE_BODY_TYPES
        or tuple(err.get("loc", ())) == ("body",)
        for err in errors
    )


# ------------------------------------------------------------------
# Register
# ------------------------------------------------------------------

def determine_rejection_reason(error_detail: Dict[str, Any], field: str) -> str:
    err_type: str = error_detail.get("type", "")
    value = error_detail.get("input")

    # 1. Faltante o vacío
    if err_type == "missing" or err_type.endswith("_too_short"):
        return "required"

    # 2. Demasiado largo
    if err_type.endswith("_too_long"):
        return "tooLong"

    # 3. Email: el orden importa (vacío > largo > formato > tipo)
    if field == "email" and isinstance(value, str):
        if value == "":
            return "required"
        if len(value) > 255:
            return "tooLong"  # email-validator falla antes por largo, con un error de formato
        return "invalidEmail"

    # 4. Todo lo demás es tipo inválido o fuera de rango (avatar: 0, 6, "a", 1.5, etc.)
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
        field=field, reason=determine_rejection_reason(error_detail, field)
    )


def handle_register_validation_error(exc: RequestValidationError) -> JSONResponse:
    field_errors = [
        fe for fe in (build_field_error(err) for err in exc.errors()) if fe is not None
    ]
    if not field_errors:
        # Body ilegible (JSON roto, vacío, array): se reportan los cinco campos
        field_errors = [
            RegisterUserFieldError(field=f, reason="required") for f in REGISTER_FIELDS
        ]

    payload = RegisterUserBadRequest(
        message="Revisá los campos marcados.",
        errors=field_errors,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(by_alias=True),
    )


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------

def _login_error(code: str, message: str) -> JSONResponse:
    payload = LogInBadRequest(code=code, message=message)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(),
    )


def handle_login_validation_error(exc: RequestValidationError) -> JSONResponse:
    """
    Traduce los errores de validación de /auth/log-in según el contrato.
    Orden de evaluación: body ilegible > invalidFieldType > incompleteForm > invalidEmail.
    """
    errors = exc.errors()
    incomplete = ("incompleteForm", "Completá el email y la contraseña.")

    # 0. Body ilegible: mismo criterio que register (todo falta)
    if is_unreadable_body(errors):
        return _login_error(*incomplete)

    # 1. Algún campo no es un string
    if any(err.get("type") == "string_type" for err in errors):
        return _login_error(
            "invalidFieldType",
            "El email y la contraseña deben ser cadenas de texto.",
        )

    # 2. Campo faltante o vacío
    if any(
        err.get("type") in ("missing", "string_too_short") or err.get("input") == ""
        for err in errors
    ):
        return _login_error(*incomplete)

    # 3. Email con formato inválido
    if any(tuple(err.get("loc", ()))[-1:] == ("email",) for err in errors):
        return _login_error("invalidEmail", "El formato del email no es válido.")

    return _login_error(*incomplete)


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