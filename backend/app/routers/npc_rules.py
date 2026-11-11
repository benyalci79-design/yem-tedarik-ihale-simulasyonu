from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import NpcRule, Product, SimulationState, Tender
from app.schemas import NpcRulePatch
from app.simulation.engine import ACTIVE_STATUSES

router = APIRouter(prefix="/api/v1/npc-rules", tags=["npc-rules"])


def serialize_rule(rule: NpcRule) -> dict:
    return {
        "id": rule.id,
        "product_id": rule.product_id,
        "product_name": rule.product.name,
        "npc_supplier_id": rule.npc_supplier_id,
        "npc_code": rule.npc_supplier.code,
        "npc_name": rule.npc_supplier.name,
        "is_invited": rule.is_invited,
        "response_probability": str(rule.response_probability),
        "min_price": str(rule.min_price),
        "max_price": str(rule.max_price),
        "min_delivery_minutes": rule.min_delivery_minutes,
        "max_delivery_minutes": rule.max_delivery_minutes,
        "freight_included": rule.freight_included,
        "min_available_kg": str(rule.min_available_kg),
        "max_available_kg": str(rule.max_available_kg),
    }


def product_has_active_tender(db: Session, product_id: int) -> bool:
    return db.scalar(
        select(Tender.id).where(
            Tender.product_id == product_id,
            Tender.status.in_(ACTIVE_STATUSES),
        ).limit(1)
    ) is not None


@router.get("")
def list_rules(
    product_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    query = select(NpcRule).order_by(NpcRule.product_id, NpcRule.npc_supplier_id)
    if product_id is not None:
        query = query.where(NpcRule.product_id == product_id)
    return {"items": [serialize_rule(rule) for rule in db.scalars(query).all()]}


@router.patch("/{rule_id}")
def update_rule(rule_id: int, payload: NpcRulePatch, db: Session = Depends(get_db)) -> dict:
    state = db.get(SimulationState, 1, with_for_update=True)
    rule = db.get(NpcRule, rule_id, with_for_update=True)
    if rule is None:
        raise ApiError(404, "NOT_FOUND", "NPC kuralı bulunamadı.")
    db.get(Product, rule.product_id, with_for_update=True)
    if state is not None and state.is_running:
        raise ApiError(409, "SETTINGS_LOCKED", "Simülasyon çalışırken NPC kuralı değiştirilemez.")
    if product_has_active_tender(db, rule.product_id):
        raise ApiError(409, "SETTINGS_LOCKED", "Üründe aktif ihale veya bekleyen teslimat varken ayar değiştirilemez.")

    values = payload.model_dump(exclude_unset=True)
    merged = {
        "is_invited": rule.is_invited,
        "response_probability": Decimal(rule.response_probability),
        "min_price": Decimal(rule.min_price),
        "max_price": Decimal(rule.max_price),
        "min_delivery_minutes": rule.min_delivery_minutes,
        "max_delivery_minutes": rule.max_delivery_minutes,
        "freight_included": rule.freight_included,
        "min_available_kg": Decimal(rule.min_available_kg),
        "max_available_kg": Decimal(rule.max_available_kg),
        **values,
    }
    if merged["max_price"] < merged["min_price"]:
        raise ApiError(422, "VALIDATION_ERROR", "Maksimum fiyat minimum fiyattan küçük olamaz.")
    if merged["max_delivery_minutes"] < merged["min_delivery_minutes"]:
        raise ApiError(422, "VALIDATION_ERROR", "Maksimum teslim süresi minimum teslim süresinden küçük olamaz.")
    if merged["max_available_kg"] < merged["min_available_kg"]:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Maksimum mevcut miktar minimum miktardan küçük olamaz.",
        )
    if not merged["is_invited"]:
        invited_exists = db.scalar(
            select(NpcRule.id).where(
                NpcRule.product_id == rule.product_id,
                NpcRule.is_invited.is_(True),
                NpcRule.id != rule.id,
            ).limit(1)
        )
        if invited_exists is None:
            raise ApiError(422, "VALIDATION_ERROR", "Ürün için en az bir davetli NPC kuralı kalmalıdır.")
    for key, value in merged.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return serialize_rule(rule)
