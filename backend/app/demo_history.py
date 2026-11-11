from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Carrier,
    NpcSupplier,
    Product,
    StockSnapshot,
    Tender,
    TenderAward,
    TenderParticipation,
)

DEMO_BASELINE_SECONDS = Decimal("1800")
ZERO = Decimal("0")
SIX_PLACES = Decimal("0.000001")
FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")
TON_KG = Decimal("1000")

HISTORY = (
    {
        "at": "300",
        "product": "MISR",
        "quantity_ton": "1.800",
        "winner": {"npc": "NPC-A", "price": "8600.00", "qty": "1200", "prep": 2, "freight": True, "carrier": None},
        "losers": [{"npc": "NPC-B", "price": "8800.00", "qty": "1500", "prep": 3, "freight": True}],
    },
    {
        "at": "600",
        "product": "ARPA",
        "quantity_ton": "1.500",
        "winner": {"npc": "NPC-B", "price": "7600.00", "qty": "1000", "prep": 1, "freight": True, "carrier": None},
        "losers": [{"npc": "NPC-D", "price": "7900.00", "qty": "1400", "prep": 4, "freight": False}],
    },
    {
        "at": "900",
        "product": "SOYA",
        "quantity_ton": "2.000",
        "winner": {"npc": "NPC-D", "price": "13000.00", "qty": "1500", "prep": 5, "freight": False, "carrier": "EKONOMIK"},
        "losers": [{"npc": "NPC-E", "price": "13300.00", "qty": "1800", "prep": 3, "freight": True}],
    },
    {
        "at": "1200",
        "product": "MISR",
        "quantity_ton": "1.500",
        "winner": {"npc": "NPC-E", "price": "8900.00", "qty": "1000", "prep": 2, "freight": True, "carrier": None},
        "losers": [{"npc": "NPC-A", "price": "9200.00", "qty": "1200", "prep": 2, "freight": True}],
    },
    {
        "at": "1500",
        "product": "ARPA",
        "quantity_ton": "1.200",
        "winner": {"npc": "NPC-A", "price": "7900.00", "qty": "800", "prep": 3, "freight": True, "carrier": None},
        "losers": [{"npc": "NPC-G", "price": "8100.00", "qty": "900", "prep": 6, "freight": False}],
    },
)


def _price_per_kg(price_per_ton: Decimal) -> Decimal:
    return (price_per_ton / TON_KG).quantize(SIX_PLACES)


def _delivery_due(accepted_at: Decimal, prep_minutes: int, assigned_at: Decimal | None, transit: int | None) -> Decimal:
    ready = accepted_at + Decimal(prep_minutes) * Decimal("60")
    if transit is None:
        return ready
    return max(ready, assigned_at or ready) + Decimal(transit) * Decimal("60")


def _add_participation(
    db: Session,
    tender: Tender,
    supplier: NpcSupplier,
    spec: dict,
    response_at: Decimal,
    accepted: bool,
) -> TenderParticipation:
    price = Decimal(spec["price"])
    quantity = Decimal(spec["qty"])
    participation = TenderParticipation(
        tender_id=tender.id,
        npc_supplier_id=supplier.id,
        response_probability=Decimal("0.900"),
        min_price=(price - Decimal("100")).quantize(TWO_PLACES),
        max_price=(price + Decimal("100")).quantize(TWO_PLACES),
        min_delivery_minutes=spec["prep"],
        max_delivery_minutes=spec["prep"],
        freight_included=bool(spec["freight"]),
        min_available_kg=quantity,
        max_available_kg=quantity,
        will_respond=True,
        response_at_seconds=response_at,
        has_offer=True,
        unit_price=price,
        delivery_minutes=spec["prep"],
        offered_quantity_kg=quantity,
        accepted_quantity_kg=quantity if accepted else ZERO,
        submitted_at_seconds=response_at,
        decision="ACCEPTED" if accepted else "REJECTED",
        decision_reason=(
            "Kullanıcı teklifin tamamını kabul etti"
            if accepted
            else "Kullanıcı tarafından kabul edilmedi"
        ),
    )
    db.add(participation)
    db.flush()
    return participation


def _seed_snapshots(db: Session, products: list[Product], purchases: dict[str, list[tuple[Decimal, Decimal, Decimal]]]) -> None:
    baseline = DEMO_BASELINE_SECONDS
    times = {baseline}
    for product_code, rows in purchases.items():
        for at, _quantity, _price in rows:
            times.add(at)
            times.add(at + Decimal("120"))
    for at in sorted(times):
        for product in products:
            final_stock = Decimal(product.current_stock_kg)
            consumption = Decimal(product.consumption_kg_per_min)
            capacity = Decimal(product.capacity_kg)
            stock = min(capacity, final_stock + consumption * (baseline - at) / Decimal("60")).quantize(SIX_PLACES)

            rows = [row for row in purchases.get(product.code, []) if row[0] <= at]
            if at == baseline or not rows:
                average = Decimal(product.avg_cost_per_kg)
            else:
                total_kg = sum((row[1] for row in rows), ZERO)
                total_cost = sum((row[1] * row[2] for row in rows), ZERO)
                average = (total_cost / total_kg).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)

            db.add(
                StockSnapshot(
                    elapsed_seconds=at,
                    product_id=product.id,
                    stock_kg=stock,
                    avg_cost_per_kg=average,
                    value_tl=(stock * average).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
                )
            )


def seed_history(db: Session) -> Decimal | None:
    """Boş veritabanına demo geçmişi ekler; doluysa dokunmaz.

    Dönen değer, geçmişin bittiği simülasyon anıdır (yeni simülasyon buradan
    devam eder). Hiç ihale yoksa beş tamamlanmış ihale, award'ları ve stok
    geçmişi oluşturulur.
    """
    if db.scalar(select(func.count(Tender.id))):
        return None

    products = {product.code: product for product in db.scalars(select(Product))}
    suppliers = {supplier.code: supplier for supplier in db.scalars(select(NpcSupplier))}
    carriers = {carrier.code: carrier for carrier in db.scalars(select(Carrier))}

    purchases: dict[str, list[tuple[Decimal, Decimal, Decimal]]] = {}
    last_price: dict[str, Decimal] = {}

    for spec in HISTORY:
        product = products.get(spec["product"])
        if product is None:
            continue
        winner = spec["winner"]
        supplier = suppliers.get(winner["npc"])
        if supplier is None:
            continue

        opened = Decimal(spec["at"])
        closes = opened + Decimal(product.offer_window_seconds)
        quantity_kg = Decimal(winner["qty"])
        price_per_ton = Decimal(winner["price"])
        transit = None
        assigned_at = None
        carrier = carriers.get(winner["carrier"]) if winner["carrier"] else None
        if carrier is not None:
            transit = carrier.transit_minutes
            assigned_at = closes + Decimal("1")
        due = _delivery_due(closes, winner["prep"], assigned_at, transit)
        landed = (quantity_kg / TON_KG * (price_per_ton + (carrier.price_per_ton if carrier else ZERO))).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        tender = Tender(
            code="TEMP",
            product_id=product.id,
            quantity_ton=Decimal(spec["quantity_ton"]),
            status="DELIVERED",
            opened_at_seconds=opened,
            offer_closes_at_seconds=closes,
            evaluate_at_seconds=closes,
            awarded_at_seconds=closes,
            delivery_due_at_seconds=due,
            delivered_at_seconds=due,
            result_reason=f"Kullanıcı {quantity_kg} kg kabul etti",
            created_at=datetime.utcnow(),
        )
        db.add(tender)
        db.flush()
        tender.code = f"YEM-{tender.id:06d}"

        winner_participation = _add_participation(db, tender, supplier, winner, opened + Decimal("1"), accepted=True)
        tender.winning_participation_id = winner_participation.id
        for loser in spec["losers"]:
            loser_supplier = suppliers.get(loser["npc"])
            if loser_supplier is None:
                continue
            _add_participation(db, tender, loser_supplier, loser, opened + Decimal("2"), accepted=False)

        db.add(
            TenderAward(
                tender_id=tender.id,
                participation_id=winner_participation.id,
                quantity_kg=quantity_kg,
                unit_price_per_ton=price_per_ton,
                freight_included=bool(winner["freight"]),
                carrier_id=carrier.id if carrier else None,
                carrier_price_per_ton=carrier.price_per_ton if carrier else None,
                status="DELIVERED",
                accepted_at_seconds=closes,
                carrier_assigned_at_seconds=assigned_at,
                delivery_due_at_seconds=due,
                delivered_at_seconds=due,
                landed_cost_tl=landed,
            )
        )

        product_code = product.code
        purchases.setdefault(product_code, []).append(
            (opened, quantity_kg, _price_per_kg(price_per_ton))
        )
        last_price[product_code] = _price_per_kg(price_per_ton)

    for code, price in last_price.items():
        product = products.get(code)
        if product is not None:
            product.last_purchase_unit_price = price

    _seed_snapshots(db, list(products.values()), purchases)
    db.flush()
    return DEMO_BASELINE_SECONDS
