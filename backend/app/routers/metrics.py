from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, StockSnapshot, TenderAward
from app.simulation.rules import price_per_ton_to_per_kg

router = APIRouter(prefix="/api/v1/stock-metrics", tags=["stock-metrics"])

ZERO = Decimal("0")
SIX_PLACES = Decimal("0.000001")
TWO_PLACES = Decimal("0.01")


def _avg(total_value: Decimal, total_stock: Decimal) -> Decimal:
    if total_stock <= ZERO:
        return ZERO
    return (total_value / total_stock).quantize(SIX_PLACES)


def _last_known_avg(costs: list[Decimal]) -> Decimal:
    """Depo tamamen boşken toplam birim fiyat, son bilinen fiyatların ortalamasıdır.

    Böylece stok 0'a düşünce gösterge 0 TL/kg'a inmez; fiyat bilgisi korunur.
    """
    if not costs:
        return ZERO
    return (sum(costs, ZERO) / Decimal(len(costs))).quantize(SIX_PLACES)


@router.get("")
def stock_metrics(db: Session = Depends(get_db)) -> dict:
    products = db.scalars(select(Product).order_by(Product.id)).all()
    items = []
    total_stock = ZERO
    total_value = ZERO
    for product in products:
        stock = Decimal(product.current_stock_kg)
        avg_cost = Decimal(product.avg_cost_per_kg)
        value = (stock * avg_cost).quantize(TWO_PLACES)
        total_stock += stock
        total_value += value
        items.append(
            {
                "product_id": product.id,
                "product_code": product.code,
                "product_name": product.name,
                "stock_kg": str(stock),
                "avg_cost_per_kg": str(avg_cost.quantize(SIX_PLACES)),
                "last_purchase_unit_price": str(Decimal(product.last_purchase_unit_price)),
                "value_tl": str(value),
            }
        )
    awards = db.scalars(select(TenderAward)).all()
    total_loss_kg = sum((Decimal(award.loss_kg) for award in awards), ZERO)
    total_loss_tl = sum(
        (
            Decimal(award.loss_kg) * price_per_ton_to_per_kg(Decimal(award.unit_price_per_ton))
            for award in awards
        ),
        ZERO,
    )
    return {
        "items": items,
        "total_stock_kg": str(total_stock),
        "total_value_tl": str(total_value.quantize(TWO_PLACES)),
        "total_avg_cost_per_kg": str(
            _avg(total_value, total_stock)
            if total_stock > ZERO
            else _last_known_avg([Decimal(product.avg_cost_per_kg) for product in products])
        ),
        "total_loss_kg": str(total_loss_kg),
        "total_loss_tl": str(total_loss_tl.quantize(TWO_PLACES)),
    }


@router.get("/history")
def stock_history(limit: int = Query(default=300, ge=2, le=3000), db: Session = Depends(get_db)) -> dict:
    """Zaman serisi; noktalar eşit aralıklı örneklenir, her nokta tek simülasyon anıdır."""
    rows = db.scalars(
        select(StockSnapshot).order_by(StockSnapshot.elapsed_seconds, StockSnapshot.product_id)
    ).all()
    grouped: dict[Decimal, list[StockSnapshot]] = {}
    for row in rows:
        grouped.setdefault(Decimal(row.elapsed_seconds), []).append(row)

    stamps = sorted(grouped)
    if len(stamps) > limit:
        step = (len(stamps) - 1) / (limit - 1)
        stamps = [stamps[round(index * step)] for index in range(limit)]

    names = {
        product.id: product.name for product in db.scalars(select(Product).order_by(Product.id)).all()
    }
    points = []
    for stamp in stamps:
        products = grouped[stamp]
        total_stock = sum((Decimal(row.stock_kg) for row in products), ZERO)
        total_value = sum((Decimal(row.value_tl) for row in products), ZERO)
        prices = [Decimal(row.avg_cost_per_kg) for row in products]
        points.append(
            {
                "elapsed_seconds": str(stamp),
                "total_stock_kg": str(total_stock),
                "total_value_tl": str(total_value.quantize(TWO_PLACES)),
                "total_avg_cost_per_kg": str(
                    _avg(total_value, total_stock) if total_stock > ZERO else _last_known_avg(prices)
                ),
                "products": [
                    {
                        "product_id": row.product_id,
                        "product_name": names.get(row.product_id, str(row.product_id)),
                        "stock_kg": str(row.stock_kg),
                        "avg_cost_per_kg": str(row.avg_cost_per_kg),
                        "value_tl": str(row.value_tl),
                    }
                    for row in products
                ],
            }
        )
    return {"items": points, "product_names": names}
