from fastapi import Request
from fastapi.responses import JSONResponse


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