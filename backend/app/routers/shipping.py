from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.errors import ApiError
from app.models import Carrier, Product, SimulationState, Tender, TenderAward
from app.runtime import engine
from app.schemas import CarrierAssign
from app.simulation.rules import delivery_due_seconds, landed_cost_tl, price_per_ton_to_per_kg

router = APIRouter(prefix="/api/v1", tags=["shipping"])

THREE_PLACES = Decimal("0.001")
ZERO = Decimal("0")


def _kg(value: Decimal) -> str:
    return str(value.quantize(THREE_PLACES))


def serialize_carrier(carrier: Carrier) -> dict:
    return {
        "id": carrier.id,
        "code": carrier.code,
        "name": carrier.name,
        "price_per_ton": str(carrier.price_per_ton),
        "price_per_kg": str(price_per_ton_to_per_kg(Decimal(carrier.price_per_ton))),
        "transit_minutes": carrier.transit_minutes,
        "is_active": carrier.is_active,
    }


def serialize_shipment(award: TenderAward, elapsed: Decimal) -> dict:
    participation = award.participation
    tender = award.tender
    remaining = None
    if award.status == "IN_TRANSIT" and award.delivery_due_at_seconds is not None:
        remaining = _kg(max(ZERO, Decimal(award.delivery_due_at_seconds) - elapsed))
    return {
        "award_id": award.id,
        "tender_id": tender.id,
        "tender_code": tender.code,
        "product_id": tender.product_id,
        "product_name": tender.product.name,
        "npc_supplier_id": participation.npc_supplier_id,
        "npc_name": participation.npc_supplier.name,
        "quantity_kg": str(award.quantity_kg),
        "unit_price_per_ton": str(award.unit_price_per_ton),
        "unit_price_per_kg": str(price_per_ton_to_per_kg(Decimal(award.unit_price_per_ton))),
        "freight_included": award.freight_included,
        "status": award.status,
        "accepted_at_seconds": str(award.accepted_at_seconds),
        "carrier_id": award.carrier_id,
        "carrier_name": award.carrier.name if award.carrier is not None else None,
        "carrier_price_per_ton": (
            str(award.carrier_price_per_ton) if award.carrier_price_per_ton is not None else None
        ),
        "carrier_assigned_at_seconds": (
            str(award.carrier_assigned_at_seconds)
            if award.carrier_assigned_at_seconds is not None
            else None
        ),
        "delivery_due_at_seconds": (
            str(award.delivery_due_at_seconds) if award.delivery_due_at_seconds is not None else None
        ),
        "delivered_at_seconds": (
            str(award.delivered_at_seconds) if award.delivered_at_seconds is not None else None
        ),
        "remaining_seconds": remaining,
        "landed_cost_tl": str(award.landed_cost_tl) if award.landed_cost_tl is not None else None,
    }


def _elapsed(db: Session) -> Decimal:
    state = db.get(SimulationState, 1)
    return Decimal(state.elapsed_seconds) if state is not None else ZERO


@router.get("/carriers")
def list_carriers(db: Session = Depends(get_db)) -> dict:
    carriers = db.scalars(
        select(Carrier).where(Carrier.is_active.is_(True)).order_by(Carrier.price_per_ton)
    ).all()
    return {"items": [serialize_carrier(carrier) for carrier in carriers]}


@router.get("/shipments")
def list_shipments(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    query = select(TenderAward).order_by(TenderAward.id.desc())
    if status is not None:
        query = query.where(TenderAward.status == status)
    elapsed = _elapsed(db)
    return {"items": [serialize_shipment(award, elapsed) for award in db.scalars(query).all()]}


@router.post("/shipments/{award_id}/assign-carrier")
def assign_carrier(award_id: int, payload: CarrierAssign) -> dict:
    engine.tick_once()
    db = SessionLocal()
    try:
        db.get(SimulationState, 1, with_for_update=True)
        tender_id = db.scalar(select(TenderAward.tender_id).where(TenderAward.id == award_id))
        if tender_id is None:
            raise ApiError(404, "NOT_FOUND", "Teslimat kaydı bulunamadı.")
        product_id = db.scalar(select(Tender.product_id).where(Tender.id == tender_id))
        if product_id is None:
            raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
        # Kilit sırası: simülasyon -> ürün -> ihale -> award.
        db.get(Product, product_id, with_for_update=True)
        db.get(Tender, tender_id, with_for_update=True)
        award = db.get(TenderAward, award_id, with_for_update=True)
        if award is None:
            raise ApiError(404, "NOT_FOUND", "Teslimat kaydı bulunamadı.")
        if award.freight_included:
            raise ApiError(
                409,
                "FREIGHT_INCLUDED",
                "Bu teslimatın nakliyesi teklife dahil; nakliyeci seçilemez.",
            )
        if award.status == "IN_TRANSIT":
            raise ApiError(409, "CARRIER_ALREADY_ASSIGNED", "Bu teslimata zaten nakliyeci atandı.")
        if award.status != "AWAITING_CARRIER":
            raise ApiError(409, "SHIPMENT_NOT_ASSIGNABLE", "Bu teslimat için nakliyeci atanamaz.")

        carrier = db.get(Carrier, payload.carrier_id)
        if carrier is None or not carrier.is_active:
            raise ApiError(404, "NOT_FOUND", "Nakliyeci bulunamadı.")

        state = db.get(SimulationState, 1)
        now = Decimal(state.elapsed_seconds) if state is not None else ZERO
        participation = award.participation
        award.carrier_id = carrier.id
        award.carrier_price_per_ton = carrier.price_per_ton
        award.carrier_assigned_at_seconds = now
        award.delivery_due_at_seconds = delivery_due_seconds(
            Decimal(award.accepted_at_seconds),
            int(participation.delivery_minutes or 0),
            now,
            carrier.transit_minutes,
        )
        award.landed_cost_tl = landed_cost_tl(
            Decimal(award.quantity_kg),
            Decimal(award.unit_price_per_ton),
            Decimal(carrier.price_per_ton),
        )
        award.status = "IN_TRANSIT"
        db.commit()
        db.refresh(award)
        return serialize_shipment(award, _elapsed(db))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
