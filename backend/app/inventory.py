from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, Tender, TenderAward
from app.simulation.rules import free_capacity_kg

INCOMING_STATUSES = ("AWAITING_CARRIER", "IN_TRANSIT")


def incoming_kg(db: Session, product_id: int) -> Decimal:
    """Yolda olan (henüz teslim edilmemiş) kabul edilmiş miktarın toplamı."""
    total = db.scalar(
        select(func.coalesce(func.sum(TenderAward.quantity_kg), 0))
        .join(Tender, Tender.id == TenderAward.tender_id)
        .where(
            Tender.product_id == product_id,
            TenderAward.status.in_(INCOMING_STATUSES),
        )
    )
    return Decimal(total or 0)


def free_capacity(db: Session, product: Product) -> Decimal:
    """Depo sınırından stok ve yoldaki miktar düşülerek kalan boş kapasite."""
    return free_capacity_kg(
        Decimal(product.capacity_kg),
        Decimal(product.current_stock_kg),
        incoming_kg(db, product.id),
    )
