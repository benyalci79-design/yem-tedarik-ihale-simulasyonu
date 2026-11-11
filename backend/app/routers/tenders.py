from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.budget import budget_state
from app.season import current_progress
from app.db import SessionLocal, get_db
from app.errors import ApiError
from app.inventory import free_capacity
from app.models import Product, SimulationState, Tender, TenderAward, TenderParticipation
from app.runtime import engine
from app.schemas import TenderAccept, TenderCreate
from app.simulation.engine import ACTIVE_STATUSES
from app.simulation.npc import schedule_response
from app.simulation.rules import (
    delivery_due_seconds,
    landed_cost_tl,
    max_acceptable_kg,
    price_per_ton_to_per_kg,
    remaining_need_kg,
    season_factor,
    season_phase,
)

router = APIRouter(prefix="/api/v1/tenders", tags=["tenders"])

THREE_PLACES = Decimal("0.001")
SIX_PLACES = Decimal("0.000001")
TON_KG = Decimal("1000")
ZERO = Decimal("0")


def _kg(value: Decimal) -> str:
    return str(value.quantize(THREE_PLACES))


def _state(db: Session) -> SimulationState:
    state = db.get(SimulationState, 1)
    if state is None:
        state = SimulationState(id=1, is_running=False, elapsed_seconds=Decimal("0"))
    return state


def _elapsed(db: Session) -> Decimal:
    return Decimal(_state(db).elapsed_seconds)


def _accepted_total(db: Session, tender_id: int) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(TenderAward.quantity_kg), 0)).where(
            TenderAward.tender_id == tender_id
        )
    )
    return Decimal(total or 0)


def _remaining_seconds(tender: Tender, elapsed: Decimal, awards: list[TenderAward]) -> str:
    if tender.status == "OPEN":
        end = Decimal(tender.offer_closes_at_seconds)
    elif tender.status == "AWARDED":
        due_values = [
            Decimal(award.delivery_due_at_seconds)
            for award in awards
            if award.status == "IN_TRANSIT" and award.delivery_due_at_seconds is not None
        ]
        end = min(due_values) if due_values else elapsed
    else:
        return "0.000"
    return _kg(max(ZERO, end - elapsed))


def _serialize_award(award: TenderAward, elapsed: Decimal) -> dict:
    participation = award.participation
    remaining = None
    if award.status == "IN_TRANSIT" and award.delivery_due_at_seconds is not None:
        remaining = _kg(max(ZERO, Decimal(award.delivery_due_at_seconds) - elapsed))
    return {
        "id": award.id,
        "participation_id": award.participation_id,
        "npc_supplier_id": participation.npc_supplier_id,
        "npc_name": participation.npc_supplier.name,
        "quantity_kg": str(award.quantity_kg),
        "unit_price_per_ton": str(award.unit_price_per_ton),
        "unit_price_per_kg": str(price_per_ton_to_per_kg(Decimal(award.unit_price_per_ton))),
        "freight_included": award.freight_included,
        "carrier_id": award.carrier_id,
        "carrier_name": award.carrier.name if award.carrier is not None else None,
        "carrier_price_per_ton": (
            str(award.carrier_price_per_ton) if award.carrier_price_per_ton is not None else None
        ),
        "status": award.status,
        "loss_kg": str(award.loss_kg),
        "accepted_kg": str(Decimal(award.quantity_kg) - Decimal(award.loss_kg)),
        "accepted_at_seconds": str(award.accepted_at_seconds),
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
        "landed_cost_tl": str(award.landed_cost_tl) if award.landed_cost_tl is not None else None,
        "remaining_seconds": remaining,
    }


def _base_tender(db: Session, tender: Tender, elapsed: Decimal) -> dict:
    awards = list(tender.awards)
    accepted_total = sum((Decimal(award.quantity_kg) for award in awards), ZERO)
    remaining = remaining_need_kg(Decimal(tender.quantity_ton), accepted_total)
    product = tender.product
    season = season_factor(
        current_progress(db),
        Decimal(product.season_amplitude),
        season_phase(product.id),
    )
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
        "remaining_seconds": _remaining_seconds(tender, elapsed, awards),
        "invited_count": len(tender.participations),
        "offer_count": sum(1 for p in tender.participations if p.has_offer),
        "accepted_total_kg": _kg(accepted_total),
        "remaining_need_kg": _kg(remaining),
        "free_capacity_kg": _kg(free_capacity(db, tender.product)),
        "product_stock_kg": str(tender.product.current_stock_kg),
        "product_capacity_kg": str(tender.product.capacity_kg),
        "product_avg_cost_per_kg": str(tender.product.avg_cost_per_kg),
        "product_last_purchase_unit_price": str(tender.product.last_purchase_unit_price),
        "product_loss_percent": str(product.loss_percent),
        "product_season_factor": str(season),
        "result_reason": tender.result_reason,
        "awards": [_serialize_award(award, elapsed) for award in awards],
    }


def _offer_details(
    db: Session,
    tender: Tender,
    include_secrets: bool,
    remaining_need_kg_value: Decimal,
) -> list[dict]:
    capacity_left = free_capacity(db, tender.product)
    result = []
    for participation in tender.participations:
        base = {
            "participation_id": participation.id,
            "npc_supplier_id": participation.npc_supplier_id,
            "npc_name": participation.npc_supplier.name,
        }
        if not include_secrets:
            base["offer_status"] = "Teklif bekleniyor"
            result.append(base)
            continue
        if not participation.has_offer or participation.unit_price is None:
            base.update(
                {
                    "offer_status": "Teklif vermedi",
                    "decision": participation.decision,
                    "decision_reason": participation.decision_reason,
                }
            )
            result.append(base)
            continue

        offered = Decimal(participation.offered_quantity_kg or 0)
        acceptable = ZERO
        if participation.decision == "PENDING" and tender.status == "EVALUATION":
            acceptable = max_acceptable_kg(offered, remaining_need_kg_value, capacity_left)
        base.update(
            {
                "offer_status": "Teklif verdi",
                "unit_price": str(participation.unit_price),
                "unit_price_per_kg": str(price_per_ton_to_per_kg(Decimal(participation.unit_price))),
                "offered_quantity_kg": str(participation.offered_quantity_kg),
                "accepted_quantity_kg": str(participation.accepted_quantity_kg),
                "delivery_minutes": participation.delivery_minutes,
                "freight_included": participation.freight_included,
                "season_factor": str(participation.season_factor),
                "submitted_at_seconds": (
                    str(participation.submitted_at_seconds)
                    if participation.submitted_at_seconds is not None
                    else None
                ),
                "decision": participation.decision,
                "decision_reason": participation.decision_reason,
                "max_acceptable_kg": _kg(acceptable),
            }
        )
        result.append(base)
    return result


def serialize_detail(db: Session, tender: Tender) -> dict:
    elapsed = _elapsed(db)
    data = _base_tender(db, tender, elapsed)
    include_secrets = tender.status != "OPEN"
    data["offers"] = _offer_details(
        db,
        tender,
        include_secrets,
        Decimal(data["remaining_need_kg"]),
    )
    data["awarded_at_seconds"] = (
        str(tender.awarded_at_seconds) if tender.awarded_at_seconds is not None else None
    )
    data["delivery_due_at_seconds"] = (
        str(tender.delivery_due_at_seconds) if tender.delivery_due_at_seconds is not None else None
    )
    data["delivered_at_seconds"] = (
        str(tender.delivered_at_seconds) if tender.delivered_at_seconds is not None else None
    )
    data["delivery_status"] = (
        "Teslim edildi"
        if tender.status == "DELIVERED"
        else "Teslim sürüyor"
        if tender.status == "AWARDED"
        else "Teslimat yok"
        if tender.status == "NO_AWARD"
        else None
    )
    data["budget_remaining_tl"] = budget_state(db)["remaining_tl"]
    return data


def _product_has_active_tender(db: Session, product_id: int) -> bool:
    return db.scalar(
        select(Tender.id).where(
            Tender.product_id == product_id,
            Tender.status.in_(ACTIVE_STATUSES),
        ).limit(1)
    ) is not None


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
    elapsed = _elapsed(db)
    return {"items": [_base_tender(db, tender, elapsed) for tender in db.scalars(query).all()]}


@router.get("/{tender_id}")
def get_tender(tender_id: int, db: Session = Depends(get_db)) -> dict:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
    return serialize_detail(db, tender)


@router.get("/{tender_id}/offers")
def get_offers(tender_id: int, db: Session = Depends(get_db)) -> dict:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
    if tender.status == "OPEN":
        raise ApiError(409, "OFFERS_HIDDEN", "Teklifler değerlendirmeye kadar gizlidir.")
    detail = serialize_detail(db, tender)
    return {"items": detail["offers"]}


@router.post("", status_code=201)
def create_tender(payload: TenderCreate) -> dict:
    engine.tick_once()
    db = SessionLocal()
    try:
        state = db.get(SimulationState, 1, with_for_update=True)
        product = db.get(Product, payload.product_id, with_for_update=True)
        if product is None:
            raise ApiError(404, "NOT_FOUND", "Ürün bulunamadı.")
        if _product_has_active_tender(db, product.id):
            raise ApiError(
                409,
                "ACTIVE_TENDER_EXISTS",
                "Bu üründe açık bir ihale veya süren teslimat var.",
            )
        rules = [rule for rule in product.npc_rules if rule.is_invited]
        if not rules:
            raise ApiError(422, "NO_INVITED_NPC", "Bu ürün için davetli NPC bulunmuyor.")

        capacity_left = free_capacity(db, product)
        required_kg = payload.quantity_ton * Decimal("1000")
        if required_kg > capacity_left:
            raise ApiError(
                422,
                "CAPACITY_EXCEEDED",
                f"Depo sınırını aşıyor. Boş kapasite: {_kg(capacity_left)} kg.",
            )

        now = Decimal(state.elapsed_seconds) if state is not None else ZERO
        closes_at = now + Decimal(product.offer_window_seconds)
        tender = Tender(
            code="TEMP",
            product_id=product.id,
            quantity_ton=payload.quantity_ton,
            status="OPEN",
            opened_at_seconds=now,
            offer_closes_at_seconds=closes_at,
            evaluate_at_seconds=closes_at,
            created_at=datetime.utcnow(),
        )
        db.add(tender)
        db.flush()
        tender.code = f"YEM-{tender.id:06d}"
        for rule in rules:
            plan = schedule_response(
                now,
                tender.offer_closes_at_seconds,
                Decimal(rule.response_probability),
                engine.rng,
            )
            db.add(
                TenderParticipation(
                    tender_id=tender.id,
                    npc_supplier_id=rule.npc_supplier_id,
                    response_probability=rule.response_probability,
                    min_price=rule.min_price,
                    max_price=rule.max_price,
                    min_delivery_minutes=rule.min_delivery_minutes,
                    max_delivery_minutes=rule.max_delivery_minutes,
                    freight_included=rule.freight_included,
                    min_available_kg=rule.min_available_kg,
                    max_available_kg=rule.max_available_kg,
                    will_respond=plan.will_respond,
                    response_at_seconds=plan.response_at_seconds,
                    has_offer=False,
                    decision="PENDING",
                )
            )
        db.commit()
        db.refresh(tender)
        return serialize_detail(db, tender)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{tender_id}/accept")
def accept_offer(tender_id: int, payload: TenderAccept) -> dict:
    engine.tick_once()
    db = SessionLocal()
    try:
        state = db.get(SimulationState, 1, with_for_update=True)
        product_id = db.scalar(select(Tender.product_id).where(Tender.id == tender_id))
        if product_id is None:
            raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
        product = db.get(Product, product_id, with_for_update=True)
        tender = db.get(Tender, tender_id, with_for_update=True)
        if product is None or tender is None:
            raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
        if tender.status != "EVALUATION":
            raise ApiError(
                409,
                "TENDER_NOT_EVALUATING",
                "Teklifler yalnızca süre dolduktan sonra kabul edilebilir.",
            )
        participation = db.get(TenderParticipation, payload.participation_id, with_for_update=True)
        if participation is None or participation.tender_id != tender.id:
            raise ApiError(404, "NOT_FOUND", "Teklif bulunamadı.")
        if not participation.has_offer or participation.offered_quantity_kg is None:
            raise ApiError(422, "OFFER_NOT_AVAILABLE", "Bu NPC teklif vermedi.")
        already = db.scalar(
            select(TenderAward.id).where(TenderAward.participation_id == participation.id).limit(1)
        )
        if already is not None:
            raise ApiError(
                409,
                "OFFER_ALREADY_ACCEPTED",
                "Bu teklif zaten kabul edildi; bir tekliften yalnızca bir kez miktar alınabilir.",
            )

        accepted_total = _accepted_total(db, tender.id)
        remaining = remaining_need_kg(Decimal(tender.quantity_ton), accepted_total)
        capacity_left = free_capacity(db, product)
        offered = Decimal(participation.offered_quantity_kg)
        quantity = payload.quantity_kg
        if quantity > capacity_left:
            raise ApiError(
                422,
                "CAPACITY_EXCEEDED",
                f"Depo sınırını aşacağı için bu miktar alınamaz. Boş kapasite: {_kg(capacity_left)} kg.",
            )
        if quantity > remaining:
            raise ApiError(
                422,
                "QUANTITY_EXCEEDS_NEED",
                f"İhalenin kalan ihtiyacı {_kg(remaining)} kg.",
            )
        if quantity > offered:
            raise ApiError(
                422,
                "QUANTITY_EXCEEDS_OFFER",
                f"NPC yalnızca {_kg(offered)} kg teklif etti.",
            )

        if participation.freight_included:
            planned_cost = landed_cost_tl(quantity, Decimal(participation.unit_price), None)
        else:
            planned_cost = (
                quantity / TON_KG * Decimal(participation.unit_price)
            ).quantize(Decimal("0.01"))
        remaining_budget = Decimal(budget_state(db)["remaining_tl"])
        if planned_cost > remaining_budget:
            raise ApiError(
                422,
                "BUDGET_EXCEEDED",
                f"Bütçe yetersiz. Kalan: {remaining_budget:.2f} TL, bu alım: {planned_cost:.2f} TL.",
            )

        now = Decimal(state.elapsed_seconds) if state is not None else ZERO
        award = TenderAward(
            tender_id=tender.id,
            participation_id=participation.id,
            quantity_kg=quantity,
            unit_price_per_ton=Decimal(participation.unit_price),
            freight_included=bool(participation.freight_included),
            accepted_at_seconds=now,
        )
        if participation.freight_included:
            award.status = "IN_TRANSIT"
            award.delivery_due_at_seconds = delivery_due_seconds(
                now, int(participation.delivery_minutes or 0), None, None
            )
            award.landed_cost_tl = landed_cost_tl(
                quantity, Decimal(participation.unit_price), None
            )
        else:
            award.status = "AWAITING_CARRIER"
        db.add(award)

        product.last_purchase_unit_price = (
            Decimal(participation.unit_price) / TON_KG
        ).quantize(SIX_PLACES)

        participation.accepted_quantity_kg = quantity
        participation.decision = "ACCEPTED" if quantity >= offered else "PARTIAL"
        participation.decision_reason = (
            "Kullanıcı teklifin tamamını kabul etti"
            if quantity >= offered
            else "Kullanıcı teklifin bir kısmını kabul etti"
        )
        db.commit()
        db.refresh(tender)
        return serialize_detail(db, tender)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{tender_id}/finalize")
def finalize_tender(tender_id: int) -> dict:
    engine.tick_once()
    db = SessionLocal()
    try:
        state = db.get(SimulationState, 1, with_for_update=True)
        product_id = db.scalar(select(Tender.product_id).where(Tender.id == tender_id))
        if product_id is None:
            raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
        db.get(Product, product_id, with_for_update=True)
        tender = db.get(Tender, tender_id, with_for_update=True)
        if tender is None:
            raise ApiError(404, "NOT_FOUND", "İhale bulunamadı.")
        if tender.status != "EVALUATION":
            raise ApiError(409, "TENDER_NOT_EVALUATING", "Bu ihale karar aşamasında değil.")

        now = Decimal(state.elapsed_seconds) if state is not None else ZERO
        awards = list(tender.awards)
        if awards:
            tender.status = "AWARDED"
            tender.awarded_at_seconds = now
            accepted_total = sum((Decimal(award.quantity_kg) for award in awards), ZERO)
            tender.result_reason = f"Kullanıcı {_kg(accepted_total)} kg kabul etti"
            if all(award.status == "DELIVERED" for award in awards):
                tender.status = "DELIVERED"
                tender.delivered_at_seconds = now
        else:
            tender.status = "NO_AWARD"
            tender.result_reason = "Kullanıcı hiçbir teklifi kabul etmedi"

        for participation in tender.participations:
            if participation.has_offer and participation.decision == "PENDING":
                participation.decision = "REJECTED"
                participation.decision_reason = "Kullanıcı tarafından kabul edilmedi"
        db.commit()
        db.refresh(tender)
        return serialize_detail(db, tender)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
