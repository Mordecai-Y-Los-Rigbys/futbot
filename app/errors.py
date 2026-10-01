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


async def register_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Manejador global para los errores de validación automáticos de Pydantic (RequestValidationError).
    Recopila todos los fallos del payload, los traduce al formato personalizado RegisterUserBadRequest 
    con estado 400 Bad Request y lista todos los campos inválidos simultáneamente en la propiedad 'errors'.
    """
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