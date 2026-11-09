from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import Product, SimulationState, Tender, TenderParticipation
from app.simulation.engine import ACTIVE_STATUSES

router = APIRouter(prefix="/api/v1/tenders", tags=["tenders"])


def _state(db: Session) -> SimulationState:
    state = db.get(SimulationState, 1)
    if state is None:
        state = SimulationState(id=1, is_running=False, elapsed_seconds=Decimal("0"))
    return state


def _remaining_seconds(tender: Tender, elapsed: Decimal) -> str:
    if tender.status == "OPEN":
        end = Decimal(tender.offer_closes_at_seconds)
    elif tender.status == "EVALUATION":
        end = Decimal(tender.evaluate_at_seconds)
    elif tender.status == "AWARDED" and tender.delivery_due_at_seconds is not None:
        end = Decimal(tender.delivery_due_at_seconds)
    else:
        return "0.000"
    return str(max(Decimal("0"), end - elapsed).quantize(Decimal("0.001")))


def _offer_count(tender: Tender) -> int:
    return sum(1 for p in tender.participations if p.has_offer)


def _base_tender(tender: Tender, elapsed: Decimal) -> dict:
    return {
        "id": tender.id,
        "code": tender.code,
        "product_id": tender.product_id,
        "product_name": tender.product.name,
        "quantity_ton": str(tender.quantity_ton),
        "status": tender.status,
        "opened_at_seconds": str(tender.opened_at_seconds),
        "offer_closes_at_seconds": str(tender.offer_closes_at_seconds),
        "evaluate_at_seconds": str(tender.evaluate_at_seconds),
        "remaining_seconds": _remaining_seconds(tender, elapsed),
        "invited_count": len(tender.participations),
        "offer_count": _offer_count(tender),
        "result_reason": tender.result_reason,
    }


def _offer_details(tender: Tender, include_secrets: bool) -> list[dict]:
    result = []
    for participation in tender.participations:
        base = {
            "participation_id": participation.id,
            "npc_supplier_id": participation.npc_supplier_id,
            "npc_name": participation.npc_supplier.name,
        }
        if not include_secrets:
            base["offer_status"] = "Teklif bekleniyor"
        elif participation.has_offer and participation.unit_price is not None:
            total = (
                Decimal(tender.quantity_ton) * Decimal(participation.unit_price)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            base.update({
                "offer_status": "Teklif verdi",
                "unit_price": str(participation.unit_price),
                "total_amount": str(total),
                "delivery_minutes": participation.delivery_minutes,
                "submitted_at_seconds": str(participation.submitted_at_seconds),
                "decision": participation.decision,
                "decision_reason": participation.decision_reason,
            })
        else:
            base.update({
                "offer_status": "Teklif vermedi",
                "decision": participation.decision,
                "decision_reason": participation.decision_reason,
            })
        result.append(base)
    return result


def serialize_detail(tender: Tender, elapsed: Decimal) -> dict:
    include_secrets = tender.status != "OPEN"
    data = _base_tender(tender, elapsed)
    data.update({
        "offers": _offer_details(tender, include_secrets),
        "awarded_at_seconds": str(tender.awarded_at_seconds) if tender.awarded_at_seconds is not None else None,
        "delivery_due_at_seconds": str(tender.delivery_due_at_seconds) if tender.delivery_due_at_seconds is not None else None,
        "delivered_at_seconds": str(tender.delivered_at_seconds) if tender.delivered_at_seconds is not None else None,
        "delivery_status": (
            "Teslim edildi" if tender.status == "DELIVERED"
            else "Bekleyen teslimat" if tender.status == "AWARDED"
            else None
        ),
    })
    return data


@router.get("")
def list_tenders(
    product_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Tender).order_by(Tender.id.desc())
    if product_id is not None:
        query = query.where(Tender.product_id == product_id)
    if status is not None:
        query = query.where(Tender.status == status)
    state = _state(db)
    return {
        "items": [_base_tender(tender, Decimal(state.elapsed_seconds)) for tender in db.scalars(query).all()]
    }


@router.get("/{tender_id}")
def get_tender(tender_id: int, db: Session = Depends(get_db)) -> dict:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
    return serialize_detail(tender, Decimal(_state(db).elapsed_seconds))


@router.get("/{tender_id}/offers")
def get_offers(tender_id: int, db: Session = Depends(get_db)) -> dict:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
    if tender.status == "OPEN":
        raise ApiError(409, "OFFERS_HIDDEN", "Teklifler değerlendirmeye kadar gizlidir.")
    return {"items": _offer_details(tender, True)}
