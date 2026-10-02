from typing import Any, Dict, List
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.auth import RegisterUserBadRequest, RegisterUserFieldError


class ApiError(Exception):
    """Error con la forma del contrato: { "code": str | None, "message": str }."""

    def __init__(self, status_code: int, code: str | None, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


def determine_rejection_reason(error_detail: Dict[str, Any]) -> str:
    """
    Analiza el tipo y el mensaje de un error de Pydantic para mapearlo 
    al motivo de rechazo exacto exigido por el contrato de la API 
    ('tooLong', 'invalidEmail' o 'required').
    """
    err_type: str = error_detail.get("type", "")
    err_msg: str = str(error_detail.get("msg", "")).lower()

    if "too_long" in err_type:
        return "tooLong"

    if "email" in err_type or "email" in err_msg:
        return "invalidEmail"

    return "required"


def build_field_error(error_detail: Dict[str, Any]) -> RegisterUserFieldError:
    """
    Procesa un detalle de error individual de Pydantic, extrae el nombre del campo 
    afectado a partir de su ubicación y determina su motivo de rechazo.
    """
    loc = error_detail.get("loc", ())
    field_name: str = str(loc[-1]) if loc else "unknown"
    reason: str = determine_rejection_reason(error_detail)

    return RegisterUserFieldError(field=field_name, reason=reason)


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
    
async def register_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Manejador global para RequestValidationError.
    Discrimina por ruta para responder según el contrato de login o de registro.
    """
    path = request.url.path.rstrip("/")
    if path.endswith("/auth/log-in") or path.endswith("/log-in"):
        return handle_login_validation_error(exc)

    field_errors: List[RegisterUserFieldError] = [
        build_field_error(err) for err in exc.errors()
    ]

    response_payload = RegisterUserBadRequest(
        message="Revisá los campos marcados.",
        errors=field_errors,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response_payload.model_dump(by_alias=True),
    )