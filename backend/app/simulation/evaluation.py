from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CandidateOffer:
    participation_id: int
    npc_supplier_id: int
    unit_price: Decimal
    delivery_minutes: int


@dataclass(frozen=True)
class EvaluationDecision:
    winner_id: int | None
    accepted_reason: str | None
    rejected_reasons: dict[int, str]
    eligible_ids: set[int]


def evaluate_offers(offers: list[CandidateOffer], coverage_minutes: Decimal) -> EvaluationDecision:
    eligible = [
        offer
        for offer in offers
        if Decimal(offer.delivery_minutes) + Decimal("0.5") <= coverage_minutes
    ]
    eligible_ids = {offer.participation_id for offer in eligible}
    if eligible:
        winner = min(eligible, key=lambda item: (item.unit_price, item.delivery_minutes, item.npc_supplier_id))
        rejected = {
            offer.participation_id: (
                "Daha uygun fiyat/sıralama nedeniyle seçilmedi"
                if offer.participation_id in eligible_ids
                else "Stok bitmeden teslim edemiyor"
            )
            for offer in offers
            if offer.participation_id != winner.participation_id
        }
        return EvaluationDecision(
            winner_id=winner.participation_id,
            accepted_reason="Uygun teslim ve fiyat sıralamasında en iyi teklif",
            rejected_reasons=rejected,
            eligible_ids=eligible_ids,
        )

    if offers:
        winner = min(offers, key=lambda item: (item.delivery_minutes, item.unit_price, item.npc_supplier_id))
        rejected = {
            offer.participation_id: "Acil kabulde daha kısa teslim/fiyat sırası nedeniyle seçilmedi"
            for offer in offers
            if offer.participation_id != winner.participation_id
        }
        return EvaluationDecision(
            winner_id=winner.participation_id,
            accepted_reason="Gecikmeli teslim riskiyle acil kabul",
            rejected_reasons=rejected,
            eligible_ids=set(),
        )

    return EvaluationDecision(None, None, {}, set())
