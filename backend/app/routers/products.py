from decimal import Decimal, ROUND_DOWN

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.inventory import free_capacity, incoming_kg
from app.models import Product, SimulationState, Tender
from app.schemas import ProductPatch
from app.simulation.engine import ACTIVE_STATUSES
from app.simulation.rules import coverage_minutes, season_factor, season_phase

router = APIRouter(prefix="/api/v1/products", tags=["products"])

MILLI_TON = Decimal("0.001")


def _active_tenders(db: Session, product_id: int) -> list[Tender]:
    return list(
        db.scalars(
            select(Tender)
            .where(Tender.product_id == product_id, Tender.status.in_(ACTIVE_STATUSES))
            .order_by(Tender.id)
        ).all()
    )


def _suggested_quantity_ton(db: Session, product: Product) -> Decimal:
    """Hedef kapsamaya ulaşmak için gereken, boş kapasiteyle sınırlı miktar (ton)."""
    stock = Decimal(product.current_stock_kg)
    incoming = incoming_kg(db, product.id)
    target_stock = Decimal(product.target_coverage_minutes) * Decimal(product.consumption_kg_per_min)
    need_kg = max(Decimal("0"), target_stock - stock - incoming)
    capacity_room = free_capacity(db, product)
    return (min(need_kg, capacity_room) / Decimal("1000")).quantize(MILLI_TON, rounding=ROUND_DOWN)


def serialize_product(db: Session, product: Product) -> dict:
    active = _active_tenders(db, product.id)
    stock = Decimal(product.current_stock_kg)
    avg_cost = Decimal(product.avg_cost_per_kg)
    state = db.get(SimulationState, 1)
    elapsed = Decimal(state.elapsed_seconds) if state is not None else Decimal("0")
    current_season = season_factor(
        elapsed,
        Decimal(product.season_amplitude),
        season_phase(product.id),
    )
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "current_stock_kg": str(product.current_stock_kg),
        "consumption_kg_per_min": str(product.consumption_kg_per_min),
        "critical_coverage_minutes": str(product.critical_coverage_minutes),
        "target_coverage_minutes": str(product.target_coverage_minutes),
        "offer_window_seconds": product.offer_window_seconds,
        "capacity_kg": str(product.capacity_kg),
        "avg_cost_per_kg": str(product.avg_cost_per_kg),
        "last_purchase_unit_price": str(product.last_purchase_unit_price),
        "loss_percent": str(product.loss_percent),
        "season_amplitude": str(product.season_amplitude),
        "season_factor": str(current_season),
        "incoming_kg": str(incoming_kg(db, product.id)),
        "free_capacity_kg": str(free_capacity(db, product)),
        "stock_value_tl": str((stock * avg_cost).quantize(Decimal("0.01"))),
        "suggested_quantity_ton": str(_suggested_quantity_ton(db, product)),
        "coverage_minutes": str(coverage_minutes(stock, Decimal(product.consumption_kg_per_min))),
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
        "capacity_kg": Decimal(product.capacity_kg),
        "avg_cost_per_kg": Decimal(product.avg_cost_per_kg),
        "loss_percent": Decimal(product.loss_percent),
        "season_amplitude": Decimal(product.season_amplitude),
        **values,
    }
    if merged["target_coverage_minutes"] <= merged["critical_coverage_minutes"]:
        raise ApiError(422, "VALIDATION_ERROR", "Hedef kapsama kritik kapsama değerinden büyük olmalıdır.")
    if merged["capacity_kg"] < merged["current_stock_kg"]:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Depo kapasitesi mevcut stoktan küçük olamaz.",
        )
    target_stock_kg = merged["target_coverage_minutes"] * merged["consumption_kg_per_min"]
    if merged["capacity_kg"] < target_stock_kg:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Depo kapasitesi hedef kapsama için gereken miktardan küçük olamaz.",
        )
    for key, value in merged.items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return serialize_product(db, product)
