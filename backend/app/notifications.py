from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.budget import budget_state, elapsed_seconds
from app.models import Product, Tender, TenderAward
from app.simulation.rules import coverage_minutes, season_factor, season_phase

ZERO = Decimal("0")
SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2}


def _notification(key: str, severity: str, title: str, detail: str, link: str) -> dict:
    return {
        "id": key,
        "severity": severity,
        "title": title,
        "detail": detail,
        "link": link,
    }


def build_notifications(db: Session) -> list[dict]:
    """Aktif uyarıları mevcut veriden üretir (okundu durumu istemcide tutulur)."""
    elapsed = elapsed_seconds(db)
    items: list[dict] = []

    products = db.scalars(select(Product).order_by(Product.id)).all()
    for product in products:
        coverage = coverage_minutes(
            Decimal(product.current_stock_kg), Decimal(product.consumption_kg_per_min)
        )
        if coverage <= Decimal(product.critical_coverage_minutes):
            items.append(
                _notification(
                    f"stock-{product.id}",
                    "warning",
                    f"{product.name} kritik kapsamada",
                    f"Kapsama {coverage.quantize(Decimal('0.1'))} dk; kritik eşik "
                    f"{product.critical_coverage_minutes} dk.",
                    "/tenders",
                )
            )
        factor = season_factor(
            elapsed, Decimal(product.season_amplitude), season_phase(product.id)
        )
        if factor >= Decimal("1.05"):
            items.append(
                _notification(
                    f"season-high-{product.id}",
                    "info",
                    f"{product.name} sezon zirvesinde",
                    f"Fiyat katsayısı ×{factor.quantize(Decimal('0.01'))}; alım maliyeti yüksek.",
                    "/tenders",
                )
            )
        elif factor <= Decimal("0.95"):
            items.append(
                _notification(
                    f"season-low-{product.id}",
                    "info",
                    f"{product.name} sezon dibinde",
                    f"Fiyat katsayısı ×{factor.quantize(Decimal('0.01'))}; alım için uygun dönem.",
                    "/tenders",
                )
            )

    for tender in db.scalars(select(Tender).where(Tender.status == "EVALUATION").order_by(Tender.id)).all():
        remaining = Decimal(tender.quantity_ton) * Decimal("1000") - sum(
            (Decimal(award.quantity_kg) for award in tender.awards), ZERO
        )
        items.append(
            _notification(
                f"tender-decision-{tender.id}",
                "warning",
                f"{tender.code} karar bekliyor",
                f"Kalan ihtiyaç {max(ZERO, remaining).quantize(Decimal('0.1'))} kg; teklifleri değerlendirin.",
                f"/tenders/{tender.id}",
            )
        )

    awards = db.scalars(
        select(TenderAward).where(TenderAward.status.in_(("AWAITING_CARRIER", "IN_TRANSIT")))
    ).all()
    for award in awards:
        tender = db.get(Tender, award.tender_id)
        product_name = tender.product.name if tender is not None else "-"
        if award.status == "AWAITING_CARRIER":
            items.append(
                _notification(
                    f"carrier-{award.id}",
                    "warning",
                    f"{product_name} için nakliyeci bekliyor",
                    f"{award.quantity_kg} kg teslimat için nakliyeci atayın.",
                    "/shipping",
                )
            )
        elif award.delivery_due_at_seconds is not None:
            remaining_seconds = Decimal(award.delivery_due_at_seconds) - elapsed
            if ZERO < remaining_seconds <= Decimal("120"):
                items.append(
                    _notification(
                        f"delivery-{award.id}",
                        "info",
                        f"{product_name} teslimatı yaklaşıyor",
                        f"Yaklaşık {remaining_seconds.quantize(Decimal('0.1'))} sn kaldı.",
                        "/shipping",
                    )
                )

    budget = budget_state(db)
    usage = Decimal(budget["usage_percent"])
    if budget["exceeded"]:
        items.append(
            _notification(
                "budget-over",
                "danger",
                "Aylık bütçe aşıldı",
                f"Harcama {budget['spent_tl']} TL; limit {budget['monthly_limit_tl']} TL.",
                "/",
            )
        )
    elif usage >= Decimal("80"):
        items.append(
            _notification(
                "budget-warning",
                "warning",
                f"Bütçenin %{usage.quantize(Decimal('0'))}'i kullanıldı",
                f"Kalan {budget['remaining_tl']} TL.",
                "/",
            )
        )

    return sorted(items, key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["id"]))
