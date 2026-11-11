from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NpcSupplier, TenderAward, TenderParticipation

ZERO = Decimal("0")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return ZERO
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))


def supplier_scores(db: Session) -> list[dict]:
    """NPC tedarikçiler için performans skorları.

    Skor = %50 fiyat rekabeti + %30 teklif verme oranı + %20 kazanma oranı.
    Fiyat rekabeti, teklifin o ihaledeki ortalama teklife göre sapmasıdır;
    ortalama altındaki teklifler tam puan alır.
    """
    suppliers = db.scalars(select(NpcSupplier).order_by(NpcSupplier.code)).all()
    participations = db.scalars(select(TenderParticipation)).all()
    awards = db.scalars(select(TenderAward)).all()

    offers_by_tender: dict[int, list[Decimal]] = {}
    for participation in participations:
        if participation.has_offer and participation.unit_price is not None:
            offers_by_tender.setdefault(participation.tender_id, []).append(
                Decimal(participation.unit_price)
            )
    tender_average = {
        tender_id: sum(prices, ZERO) / Decimal(len(prices))
        for tender_id, prices in offers_by_tender.items()
        if prices
    }

    awarded_participations = {award.participation_id for award in awards}

    rows: list[dict] = []
    for supplier in suppliers:
        own = [p for p in participations if p.npc_supplier_id == supplier.id]
        invitations = len(own)
        offered = [p for p in own if p.has_offer]
        wins = [p for p in offered if p.id in awarded_participations]
        deviations: list[Decimal] = []
        delivery_times: list[int] = []
        for participation in offered:
            average = tender_average.get(participation.tender_id)
            if average is not None and average > ZERO and participation.unit_price is not None:
                deviation = (
                    (Decimal(participation.unit_price) - average) / average * HUNDRED
                ).quantize(TWO_PLACES)
                deviations.append(deviation)
            if participation.delivery_minutes is not None:
                delivery_times.append(participation.delivery_minutes)

        avg_deviation = (
            (sum(deviations, ZERO) / Decimal(len(deviations))).quantize(TWO_PLACES)
            if deviations
            else ZERO
        )
        response_rate = _ratio(len(offered), invitations)
        win_rate = _ratio(len(wins), len(offered))
        price_score = max(ZERO, min(Decimal("1"), Decimal("1") - avg_deviation / Decimal("20")))
        if not offered:
            score = ZERO
        else:
            score = (
                price_score * Decimal("0.5") + response_rate * Decimal("0.3") + win_rate * Decimal("0.2")
            ) * HUNDRED
        rows.append(
            {
                "supplier_id": supplier.id,
                "code": supplier.code,
                "name": supplier.name,
                "invitations": invitations,
                "offers": len(offered),
                "awards": len(wins),
                "response_rate": str(response_rate),
                "win_rate": str(win_rate),
                "avg_price_deviation_pct": str(avg_deviation),
                "avg_delivery_minutes": str(
                    (Decimal(sum(delivery_times)) / Decimal(len(delivery_times))).quantize(TWO_PLACES)
                    if delivery_times
                    else ZERO
                ),
                "score": str(score.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            }
        )
    return sorted(rows, key=lambda row: Decimal(row["score"]), reverse=True)
