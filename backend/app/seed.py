from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Carrier, NpcRule, NpcSupplier, Product, SimulationState

TWO_PLACES = Decimal("0.01")

# (kod, ad, stok, tüketim, kritik kapsama, hedef kapsama, teklif penceresi,
#  depo kapasitesi, stoktaki ortalama birim maliyet)
PRODUCTS = (
    ("MISR", "Dane Mısır", Decimal("900"), Decimal("100"), Decimal("10"), Decimal("30"), 60, Decimal("5000.000"), Decimal("8.750000")),
    ("ARPA", "Arpa", Decimal("700"), Decimal("80"), Decimal("10"), Decimal("30"), 60, Decimal("4000.000"), Decimal("7.750000")),
    ("SOYA", "Soya Küspesi", Decimal("3000"), Decimal("60"), Decimal("10"), Decimal("30"), 60, Decimal("6000.000"), Decimal("13.000000")),
)

# (kod, ad, cevap olasılığı, fiyat çarpanı, min teslim, max teslim,
#  nakliye dahil, min mevcut kg, max mevcut kg)
NPCS = (
    ("NPC-A", "Örnek Yem A", Decimal("1.000"), Decimal("1.00"), 1, 3, True, Decimal("1000"), Decimal("3000")),
    ("NPC-B", "Örnek Yem B", Decimal("0.600"), Decimal("1.00"), 1, 3, True, Decimal("1000"), Decimal("3000")),
    # C hiç cevap vermez: davet edilir ama teklif üretmez (demo senaryosu).
    ("NPC-C", "Örnek Yem C", Decimal("0.000"), Decimal("1.00"), 1, 3, True, Decimal("1000"), Decimal("3000")),
    ("NPC-D", "Ege Yem Ltd.", Decimal("0.850"), Decimal("0.98"), 4, 8, True, Decimal("3000"), Decimal("6000")),
    ("NPC-E", "Anadolu Tarım", Decimal("0.900"), Decimal("1.05"), 2, 5, True, Decimal("1500"), Decimal("3500")),
    ("NPC-F", "Marmara Lojistik Yem", Decimal("0.700"), Decimal("0.90"), 5, 8, False, Decimal("3000"), Decimal("6000")),
    ("NPC-G", "Karadeniz Yem", Decimal("0.550"), Decimal("0.92"), 3, 7, False, Decimal("1000"), Decimal("2500")),
    ("NPC-H", "Hızlı Tedarik", Decimal("0.800"), Decimal("0.93"), 1, 2, False, Decimal("300"), Decimal("1000")),
    ("NPC-I", "Güneydoğu Yem", Decimal("0.450"), Decimal("0.95"), 6, 8, False, Decimal("4000"), Decimal("6000")),
    ("NPC-J", "Trakya Yem", Decimal("0.950"), Decimal("1.10"), 2, 4, True, Decimal("500"), Decimal("1500")),
)

PRICE_RANGES = {
    "MISR": (Decimal("8000.00"), Decimal("9500.00")),
    "ARPA": (Decimal("7000.00"), Decimal("8500.00")),
    "SOYA": (Decimal("12000.00"), Decimal("14000.00")),
}

# (kod, ad, TL/ton, taşıma süresi (simülasyon dakikası))
CARRIERS = (
    ("EKONOMIK", "Ekonomik Nakliye", Decimal("180.00"), 8),
    ("STANDART", "Standart Nakliye", Decimal("450.00"), 5),
    ("EKSPRES", "Ekspres Nakliye", Decimal("900.00"), 2),
    ("TOPLU", "Toplu Yük", Decimal("150.00"), 12),
)

LEGACY_PRODUCT_CODES = {
    "MISR": ("MISIR",),
}


def _price_range(product_code: str, factor: Decimal) -> tuple[Decimal, Decimal]:
    base_min, base_max = PRICE_RANGES[product_code]
    return (
        (base_min * factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        (base_max * factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
    )


def main() -> None:
    """Eksik seed kayıtlarını ekler; var olan ayarları ve planları değiştirmez."""
    with SessionLocal.begin() as db:
        state = db.get(SimulationState, 1)
        if state is None:
            db.add(SimulationState(id=1, is_running=False, elapsed_seconds=Decimal("0")))

        products_by_code: dict[str, Product] = {}
        for (
            code,
            name,
            stock,
            consumption,
            critical,
            target,
            window,
            capacity,
            avg_cost,
        ) in PRODUCTS:
            product = db.scalar(select(Product).where(Product.code == code))
            if product is None:
                for legacy_code in LEGACY_PRODUCT_CODES.get(code, ()):
                    product = db.scalar(select(Product).where(Product.code == legacy_code))
                    if product is not None:
                        break
            if product is None:
                product = Product(
                    code=code,
                    name=name,
                    current_stock_kg=stock,
                    consumption_kg_per_min=consumption,
                    critical_coverage_minutes=critical,
                    target_coverage_minutes=target,
                    offer_window_seconds=window,
                    capacity_kg=capacity,
                    avg_cost_per_kg=avg_cost,
                    next_eligible_at_seconds=Decimal("0"),
                )
                db.add(product)
                db.flush()
            products_by_code[code] = product

        suppliers_by_code: dict[str, NpcSupplier] = {}
        for code, name, *_rest in NPCS:
            supplier = db.scalar(select(NpcSupplier).where(NpcSupplier.code == code))
            if supplier is None:
                supplier = NpcSupplier(code=code, name=name)
                db.add(supplier)
                db.flush()
            suppliers_by_code[code] = supplier

        for product_code, product in products_by_code.items():
            for (
                npc_code,
                _npc_name,
                probability,
                price_factor,
                min_delivery,
                max_delivery,
                freight_included,
                min_available,
                max_available,
            ) in NPCS:
                supplier = suppliers_by_code[npc_code]
                rule = db.scalar(
                    select(NpcRule).where(
                        NpcRule.product_id == product.id,
                        NpcRule.npc_supplier_id == supplier.id,
                    )
                )
                if rule is not None:
                    continue
                min_price, max_price = _price_range(product_code, price_factor)
                db.add(
                    NpcRule(
                        product_id=product.id,
                        npc_supplier_id=supplier.id,
                        is_invited=True,
                        response_probability=probability,
                        min_price=min_price,
                        max_price=max_price,
                        min_delivery_minutes=min_delivery,
                        max_delivery_minutes=max_delivery,
                        freight_included=freight_included,
                        min_available_kg=min_available,
                        max_available_kg=max_available,
                    )
                )

        for code, name, price_per_ton, transit_minutes in CARRIERS:
            carrier = db.scalar(select(Carrier).where(Carrier.code == code))
            if carrier is None:
                db.add(
                    Carrier(
                        code=code,
                        name=name,
                        price_per_ton=price_per_ton,
                        transit_minutes=transit_minutes,
                        is_active=True,
                    )
                )


if __name__ == "__main__":
    main()
