from typing import Any, Dict, List
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.auth import RegisterUserBadRequest, RegisterUserFieldError

REGISTER_FIELDS = ("username", "email", "password", "clubName", "avatar")


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
            return "tooLong"   # email-validator falla antes por largo, con un error de formato
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


def handle_login_validation_error(exc: RequestValidationError) -> JSONResponse:
    """
    Traduce los errores de validación de Pydantic para /auth/log-in según el contrato:
    - invalidFieldType: Si algún campo no es un string.
    - incompleteForm: Si falta algún campo o se envió vacío ("").
    - invalidEmail: Si el email tiene formato inválido.
    """
    errors = exc.errors()

    # 1. Comprobar tipos incorrectos (ej: int, bool, list en vez de str)
    for err in errors:
        err_type = str(err.get("type", ""))
        # Captura errores de tipo de Pydantic (string_type, etc.)
        if "type" in err_type and "missing" not in err_type:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "code": "invalidFieldType",
                    "message": "El email y la contraseña deben ser cadenas de texto.",
                },
            )

    # 2. Comprobar campos faltantes o vacíos ("")
    for err in errors:
        err_type = str(err.get("type", ""))
        val_input = err.get("input")
        # Si falta el campo ('missing'), es string vacío (""), o falló por min_length / too_short
        if (
            "missing" in err_type
            or "too_short" in err_type
            or val_input == ""
            or (isinstance(val_input, str) and len(val_input) == 0)
        ):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "code": "incompleteForm",
                    "message": "Completá el email y la contraseña.",
                },
            )

    # 3. Comprobar formato de email inválido (cuando sí viene un valor pero no cumple RFC)
    for err in errors:
        err_type = str(err.get("type", ""))
        err_msg = str(err.get("msg", "")).lower()
        loc = tuple(err.get("loc", ()))
        if "email" in err_type or "email" in err_msg or "email" in loc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "code": "invalidEmail",
                    "message": "El formato del email no es válido.",
                },
            )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": "incompleteForm",
            "message": "Completá el email y la contraseña.",
        },
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


def handle_generic_validation_error(exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    only_missing = all(err.get("type") == "missing" for err in errors)
    body_unreadable = any(
        err.get("type") in ("json_invalid", "model_attributes_type")
        or tuple(err.get("loc", ())) == ("body",)
        for err in errors
    )

    if only_missing or body_unreadable:
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


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    path = request.url.path.rstrip("/")
    handler = VALIDATION_HANDLERS.get(path, handle_generic_validation_error)
    return handler(exc)