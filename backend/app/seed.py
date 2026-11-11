from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import NpcRule, NpcSupplier, Product, SimulationState

PRODUCTS = (
    ("MISR", "Dane Mısır", Decimal("900"), Decimal("100"), Decimal("10"), Decimal("30"), 60),
    ("ARPA", "Arpa", Decimal("700"), Decimal("80"), Decimal("10"), Decimal("30"), 60),
    ("SOYA", "Soya Küspesi", Decimal("3000"), Decimal("60"), Decimal("10"), Decimal("30"), 60),
)
NPCS = (
    ("NPC-A", "Örnek Yem A", Decimal("1.000")),
    ("NPC-B", "Örnek Yem B", Decimal("0.600")),
    ("NPC-C", "Örnek Yem C", Decimal("0.000")),
)
PRICE_RANGES = {
    "MISR": (Decimal("8000.00"), Decimal("9500.00")),
    "ARPA": (Decimal("7000.00"), Decimal("8500.00")),
    "SOYA": (Decimal("12000.00"), Decimal("14000.00")),
}
LEGACY_PRODUCT_CODES = {
    "MISR": ("MISIR",),
}


def main() -> None:
    """Eksik seed kayıtlarını ekler; var olan ayarları ve planları değiştirmez."""
    with SessionLocal.begin() as db:
        state = db.get(SimulationState, 1)
        if state is None:
            db.add(SimulationState(id=1, is_running=False, elapsed_seconds=Decimal("0")))

        products_by_code: dict[str, Product] = {}
        for code, name, stock, consumption, critical, target, window in PRODUCTS:
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
                    next_eligible_at_seconds=Decimal("0"),
                )
                db.add(product)
                db.flush()
            products_by_code[code] = product

        suppliers_by_code: dict[str, NpcSupplier] = {}
        for code, name, _probability in NPCS:
            supplier = db.scalar(select(NpcSupplier).where(NpcSupplier.code == code))
            if supplier is None:
                supplier = NpcSupplier(code=code, name=name)
                db.add(supplier)
                db.flush()
            suppliers_by_code[code] = supplier

        for product_code, product in products_by_code.items():
            min_price, max_price = PRICE_RANGES[product_code]
            for npc_code, _npc_name, probability in NPCS:
                supplier = suppliers_by_code[npc_code]
                rule = db.scalar(
                    select(NpcRule).where(
                        NpcRule.product_id == product.id,
                        NpcRule.npc_supplier_id == supplier.id,
                    )
                )
                if rule is None:
                    db.add(
                        NpcRule(
                            product_id=product.id,
                            npc_supplier_id=supplier.id,
                            is_invited=True,
                            response_probability=probability,
                            min_price=min_price,
                            max_price=max_price,
                            min_delivery_minutes=1,
                            max_delivery_minutes=3,
                        )
                    )


if __name__ == "__main__":
    main()
