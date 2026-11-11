from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.notifications import build_notifications

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
def list_notifications(db: Session = Depends(get_db)) -> dict:
    return {"items": build_notifications(db)}
