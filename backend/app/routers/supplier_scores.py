from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.suppliers import supplier_scores

router = APIRouter(prefix="/api/v1/supplier-scores", tags=["suppliers"])


@router.get("")
def list_supplier_scores(db: Session = Depends(get_db)) -> dict:
    return {"items": supplier_scores(db)}
