from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, Tender, TenderAward
from app.simulation.rules import TON_KG

ZERO = Decimal("0")
SIX_PLACES = Decimal("0.000001")


def mal_price_per_kg(award: TenderAward) -> Decimal:
    """Kabul edilen alımın kg başına mal fiyatı (nakliye hariç)."""
    return (Decimal(award.unit_price_per_ton) / TON_KG).quantize(SIX_PLACES)


def purchase_stats(db: Session, product: Product) -> dict:
    """Ürünün alım geçmişinden son/en ucuz/en pahalı/ortalama birim fiyatları.

    Ortalama, miktar ağırlıklıdır (toplam mal bedeli / toplam kg). Hiç alım
    yoksa yalnızca son alım alanı (başlangıç maliyeti) dolu döner.
    """
    awards = db.scalars(
        select(TenderAward)
        .join(Tender, Tender.id == TenderAward.tender_id)
        .where(Tender.product_id == product.id)
        .order_by(TenderAward.accepted_at_seconds, TenderAward.id)
    ).all()
    if not awards:
        return {
            "product_id": product.id,
            "product_code": product.code,
            "product_name": product.name,
            "purchase_count": 0,
            "last_unit_price": str(Decimal(product.last_purchase_unit_price)),
            "min_unit_price": None,
            "max_unit_price": None,
            "avg_unit_price": None,
        }

    prices = [mal_price_per_kg(award) for award in awards]
    total_kg = sum((Decimal(award.quantity_kg) for award in awards), ZERO)
    total_cost = sum(
        (mal_price_per_kg(award) * Decimal(award.quantity_kg) for award in awards), ZERO
    )
    average = (total_cost / total_kg).quantize(SIX_PLACES) if total_kg > ZERO else ZERO
    return {
        "product_id": product.id,
        "product_code": product.code,
        "product_name": product.name,
        "purchase_count": len(awards),
        "last_unit_price": str(Decimal(product.last_purchase_unit_price) or prices[-1]),
        "min_unit_price": str(min(prices)),
        "max_unit_price": str(max(prices)),
        "avg_unit_price": str(average),
    }
