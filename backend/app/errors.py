from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import NoResultFound


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(content=error_body(exc.code, exc.message), status_code=exc.status_code)


async def validation_error_handler(_request: Request, _exc: ValidationError) -> JSONResponse:
    return JSONResponse(content=error_body("VALIDATION_ERROR", "Gönderilen alanları kontrol edin."), status_code=422)


async def generic_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(content=error_body("INTERNAL_ERROR", "İşlem gerçekleştirilemedi."), status_code=500)
