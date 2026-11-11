from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import Product, SimulationState, Tender
from app.schemas import ProductPatch
from app.simulation.engine import ACTIVE_STATUSES
from app.simulation.rules import coverage_minutes

router = APIRouter(prefix="/api/v1/products", tags=["products"])


def _active_tenders(db: Session, product_id: int) -> list[Tender]:
    return list(
        db.scalars(
            select(Tender)
            .where(Tender.product_id == product_id, Tender.status.in_(ACTIVE_STATUSES))
            .order_by(Tender.id)
        ).all()
    )


def serialize_product(db: Session, product: Product) -> dict:
    active = _active_tenders(db, product.id)
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "current_stock_kg": str(product.current_stock_kg),
        "consumption_kg_per_min": str(product.consumption_kg_per_min),
        "critical_coverage_minutes": str(product.critical_coverage_minutes),
        "target_coverage_minutes": str(product.target_coverage_minutes),
        "offer_window_seconds": product.offer_window_seconds,
        "coverage_minutes": str(coverage_minutes(
            Decimal(product.current_stock_kg),
            Decimal(product.consumption_kg_per_min),
        )),
        "active_tenders": [
            {"id": tender.id, "code": tender.code, "status": tender.status}
            for tender in active
        ],
    }


@router.get("")
def list_products(db: Session = Depends(get_db)) -> dict:
    return {"items": [serialize_product(db, product) for product in db.scalars(select(Product).order_by(Product.id)).all()]}


@router.patch("/{product_id}")
def update_product(product_id: int, payload: ProductPatch, db: Session = Depends(get_db)) -> dict:
    # Motor tick'i de önce simülasyon sonra ürün satırını kilitler; aynı sıra
    # ayar değişikliğinde korunarak ara durumda kısmi güncelleme önlenir.
    state = db.get(SimulationState, 1, with_for_update=True)
    product = db.get(Product, product_id, with_for_update=True)
    if product is None:
        raise ApiError(404, "NOT_FOUND", "Ürün bulunamadı.")
    if state is not None and state.is_running:
        raise ApiError(409, "SETTINGS_LOCKED", "Simülasyon çalışırken ürün ayarı değiştirilemez.")
    if _active_tenders(db, product.id):
        raise ApiError(409, "SETTINGS_LOCKED", "Üründe aktif ihale veya bekleyen teslimat varken ayar değiştirilemez.")

    values = payload.model_dump(exclude_unset=True)
    merged = {
        "current_stock_kg": Decimal(product.current_stock_kg),
        "consumption_kg_per_min": Decimal(product.consumption_kg_per_min),
        "critical_coverage_minutes": Decimal(product.critical_coverage_minutes),
        "target_coverage_minutes": Decimal(product.target_coverage_minutes),
        "offer_window_seconds": product.offer_window_seconds,
        **values,
    }
    if merged["target_coverage_minutes"] <= merged["critical_coverage_minutes"]:
        raise ApiError(422, "VALIDATION_ERROR", "Hedef kapsama kritik kapsama değerinden büyük olmalıdır.")
    for key, value in merged.items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return serialize_product(db, product)
