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
    return JSONResponse(exc.status_code, error_body(exc.code, exc.message))


async def validation_error_handler(_request: Request, _exc: ValidationError) -> JSONResponse:
    return JSONResponse(422, error_body("VALIDATION_ERROR", "Gönderilen alanları kontrol edin."))


async def generic_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(500, error_body("INTERNAL_ERROR", "İşlem gerçekleştirilemedi."))
