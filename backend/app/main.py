import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import SessionLocal
from app.errors import ApiError, api_error_handler, generic_error_handler, validation_error_handler
from app.routers import npc_rules, products, simulation, tenders
from app.runtime import start_runtime, stop_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = await start_runtime()
    try:
        yield
    finally:
        await stop_runtime(task)


app = FastAPI(title="Yem İhale Simülasyonu", version="4.0.0", lifespan=lifespan)
app.include_router(simulation.router)
app.include_router(products.router)
app.include_router(npc_rules.router)
app.include_router(tenders.router)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(exc.status_code, exc.detail)
    return JSONResponse(exc.status_code, {"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}})


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # SQL/stack trace istemciye sızdırılmaz.
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "DB_UNAVAILABLE", "message": "Veritabanı hazır değil."}},
        ) from exc
