from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product
from app.purchases import purchase_stats

router = APIRouter(prefix="/api/v1/purchase-stats", tags=["purchases"])


@router.get("")
def list_purchase_stats(db: Session = Depends(get_db)) -> dict:
    products = db.scalars(select(Product).order_by(Product.id)).all()
    return {"items": [purchase_stats(db, product) for product in products]}
