from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.db import SessionLocal

app = FastAPI(title="Yem İhale Simülasyonu", version="4.0.0")


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
