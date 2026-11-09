from __future__ import annotations

import threading
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Protocol

from sqlalchemy import select

from app.db import SessionLocal
from app.models import NpcRule, Product, SimulationState, Tender, TenderParticipation
from app.simulation.evaluation import CandidateOffer, evaluate_offers
from app.simulation.npc import DefaultRng, Rng, generate_offer, schedule_response
from app.simulation.rules import consume_stock, coverage_minutes, deliver_stock_once, tender_quantity_ton
from app.simulation.timeline import TimelineEvent, ordered_events

ACTIVE_STATUSES = ("OPEN", "EVALUATION", "AWARDED")
ZERO = Decimal("0")
THIRTY_SECONDS = Decimal("30")
THOUSANDTH = Decimal("0.001")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.utcnow()


def decimal_seconds(value: float) -> Decimal:
    return Decimal(str(value)).quantize(THOUSANDTH, rounding=ROUND_HALF_UP)


class SimulationEngine:
    """Tek worker için kilitli, kronolojik ve kontrollü simülasyon motoru."""

    def __init__(
        self,
        session_factory: Callable = SessionLocal,
        clock: Clock | None = None,
        rng: Rng | None = None,
    ):
        self.session_factory = session_factory
        self.clock = clock or SystemClock()
        self.rng = rng or DefaultRng()
        self._lock = threading.RLock()

    def initialize_after_restart(self) -> None:
        """Kapanmış gerçek zamanı simülasyona taşımadan servisi duraklatır."""
        with self._lock, self.session_factory.begin() as db:
            state = db.get(SimulationState, 1, with_for_update=True)
            if state is None:
                state = SimulationState(id=1, is_running=False, elapsed_seconds=ZERO)
                db.add(state)
            else:
                state.is_running = False
                state.last_tick_at = None
                state.last_error = None

    def start(self) -> SimulationState:
        with self._lock, self.session_factory.begin() as db:
            state = db.get(SimulationState, 1, with_for_update=True)
            if state is None:
                state = SimulationState(id=1, is_running=False, elapsed_seconds=ZERO)
                db.add(state)
            if not state.is_running:
                state.is_running = True
                state.last_tick_at = self.clock.now()
                state.last_error = None
            return state

    def pause(self) -> SimulationState:
        with self._lock:
            self.tick_once()
            with self.session_factory.begin() as db:
                state = db.get(SimulationState, 1, with_for_update=True)
                if state is not None:
                    state.is_running = False
                    state.last_tick_at = None
                return state

    def tick_once(self) -> SimulationState | None:
        with self._lock:
            return self._tick_locked(self.clock.now())

    def _tick_locked(self, now: datetime) -> SimulationState | None:
        db = self.session_factory()
        try:
            state = db.get(SimulationState, 1, with_for_update=True)
            if state is None or not state.is_running:
                return state
            if state.last_tick_at is None:
                state.last_tick_at = now
                db.commit()
                return state

            delta = decimal_seconds((now - state.last_tick_at).total_seconds())
            if delta <= ZERO:
                return state

            current = Decimal(state.elapsed_seconds)
            target = current + delta
            self._process_interval(db, current, target)
            state.elapsed_seconds = target
            state.last_tick_at = now
            state.last_error = None
            db.commit()
            return state
        except Exception:
            db.rollback()
            self._pause_with_error()
            return None
        finally:
            db.close()

    def _pause_with_error(self) -> None:
        with self.session_factory.begin() as db:
            state = db.get(SimulationState, 1, with_for_update=True)
            if state is not None:
                state.is_running = False
                state.last_tick_at = None
                state.last_error = "Simülasyon olayı işlenemedi; simülasyon duraklatıldı."

    def _process_interval(self, db, current: Decimal, target: Decimal) -> None:
        cursor = current
        while True:
            events = self._events_between(db, cursor, target)
            if not events:
                self._consume_all(db, target - cursor)
                cursor = target
                break

            event_time = min(event[0] for event in events)
            self._consume_all(db, event_time - cursor)
            cursor = event_time
            same_time = [
                TimelineEvent(at_seconds=event[0], kind=event[2], object_id=event[3])
                for event in events
                if event[0] == event_time
            ]
            for event in ordered_events(same_time):
                self._process_event(db, event.kind, event.object_id, cursor)

        state = db.get(SimulationState, 1, with_for_update=True)
        if state is not None:
            state.elapsed_seconds = cursor
        self._open_needed_tenders(db, cursor)

    def _consume_all(self, db, elapsed_seconds: Decimal) -> None:
        if elapsed_seconds <= ZERO:
            return
        for product in db.scalars(select(Product).order_by(Product.id)).all():
            product.current_stock_kg = consume_stock(
                Decimal(product.current_stock_kg),
                Decimal(product.consumption_kg_per_min),
                elapsed_seconds,
            )

    def _events_between(self, db, current: Decimal, target: Decimal) -> list[tuple[Decimal, int, str, int]]:
        events: list[tuple[Decimal, int, str, int]] = []
        for tender in db.scalars(select(Tender).order_by(Tender.id)).all():
            if tender.status == "AWARDED" and tender.delivery_due_at_seconds is not None:
                due = Decimal(tender.delivery_due_at_seconds)
                if current < due <= target:
                    events.append((due, 0, "delivery", tender.id))
            if tender.status == "OPEN":
                close = Decimal(tender.offer_closes_at_seconds)
                if current < close <= target:
                    events.append((close, 3, "close", tender.id))
                for participation in tender.participations:
                    if (
                        participation.will_respond
                        and not participation.has_offer
                        and participation.response_at_seconds is not None
                    ):
                        response_at = Decimal(participation.response_at_seconds)
                        if current < response_at <= target:
                            events.append((response_at, 2, "response", participation.id))
            if tender.status == "EVALUATION":
                evaluate_at = Decimal(tender.evaluate_at_seconds)
                if current < evaluate_at <= target:
                    events.append((evaluate_at, 4, "evaluate", tender.id))
        return events

    def _process_event(self, db, kind: str, object_id: int, event_time: Decimal) -> None:
        if kind == "delivery":
            tender = db.get(Tender, object_id, with_for_update=True)
            if tender is not None:
                self._deliver_tender(db, tender, event_time)
        elif kind == "response":
            participation = db.get(TenderParticipation, object_id, with_for_update=True)
            if participation is not None:
                self._submit_offer(db, participation, event_time)
        elif kind == "close":
            tender = db.get(Tender, object_id, with_for_update=True)
            if tender is not None and tender.status == "OPEN":
                tender.status = "EVALUATION"
        elif kind == "evaluate":
            tender = db.get(Tender, object_id, with_for_update=True)
            if tender is not None:
                self._evaluate_tender(db, tender, event_time)

    def _submit_offer(self, db, participation: TenderParticipation, event_time: Decimal) -> None:
        tender = db.get(Tender, participation.tender_id)
        if (
            tender is None
            or tender.status != "OPEN"
            or participation.has_offer
            or participation.response_at_seconds is None
            or Decimal(participation.response_at_seconds) >= Decimal(tender.offer_closes_at_seconds)
        ):
            return
        offer = generate_offer(
            Decimal(participation.min_price),
            Decimal(participation.max_price),
            participation.min_delivery_minutes,
            participation.max_delivery_minutes,
            self.rng,
        )
        participation.has_offer = True
        participation.unit_price = offer.unit_price
        participation.delivery_minutes = offer.delivery_minutes
        participation.submitted_at_seconds = event_time
        participation.decision = "PENDING"

    def _evaluate_tender(self, db, tender: Tender, event_time: Decimal) -> None:
        if tender.status != "EVALUATION":
            return
        product = db.get(Product, tender.product_id, with_for_update=True)
        if product is None:
            return
        stock = Decimal(product.current_stock_kg)
        consumption = Decimal(product.consumption_kg_per_min)
        coverage = coverage_minutes(stock, consumption)
        tender.evaluated_stock_kg = stock
        tender.evaluated_consumption_kg_per_min = consumption
        tender.evaluated_coverage_minutes = coverage

        offers = [
            CandidateOffer(
                participation_id=participation.id,
                npc_supplier_id=participation.npc_supplier_id,
                unit_price=Decimal(participation.unit_price),
                delivery_minutes=participation.delivery_minutes,
            )
            for participation in tender.participations
            if participation.has_offer and participation.unit_price is not None and participation.delivery_minutes is not None
        ]
        decision = evaluate_offers(offers, coverage)
        if decision.winner_id is None:
            tender.status = "NO_AWARD"
            tender.result_reason = "Hiç gerçek teklif alınamadı"
            product.next_eligible_at_seconds = event_time + THIRTY_SECONDS
            return

        for participation in tender.participations:
            if not participation.has_offer:
                continue
            if participation.id == decision.winner_id:
                participation.decision = "ACCEPTED"
                participation.decision_reason = decision.accepted_reason
                tender.winning_participation_id = participation.id
                tender.awarded_at_seconds = event_time
                tender.delivery_due_at_seconds = event_time + Decimal(participation.delivery_minutes) * Decimal("60")
            else:
                participation.decision = "REJECTED"
                participation.decision_reason = decision.rejected_reasons.get(
                    participation.id, "Daha uygun fiyat/sıralama nedeniyle seçilmedi"
                )
        tender.status = "AWARDED"

    def _deliver_tender(self, db, tender: Tender, event_time: Decimal) -> None:
        if tender.status != "AWARDED" or tender.delivered_at_seconds is not None:
            return
        product = db.get(Product, tender.product_id, with_for_update=True)
        if product is None:
            return
        new_stock, new_status, changed = deliver_stock_once(
            tender.status,
            tender.delivered_at_seconds,
            Decimal(product.current_stock_kg),
            Decimal(tender.quantity_ton),
        )
        if changed:
            product.current_stock_kg = new_stock
            tender.delivered_at_seconds = event_time
            tender.status = new_status

    def _open_needed_tenders(self, db, now: Decimal) -> None:
        products = db.scalars(select(Product).order_by(Product.id)).all()
        for product in products:
            if now < Decimal(product.next_eligible_at_seconds):
                continue
            active = db.scalar(
                select(Tender.id).where(
                    Tender.product_id == product.id,
                    Tender.status.in_(ACTIVE_STATUSES),
                ).limit(1)
            )
            if active is not None:
                continue
            if coverage_minutes(
                Decimal(product.current_stock_kg),
                Decimal(product.consumption_kg_per_min),
            ) > Decimal(product.critical_coverage_minutes):
                continue
            rules = [
                rule for rule in product.npc_rules
                if rule.is_invited
            ]
            if not rules:
                continue
            tender = Tender(
                code="TEMP",
                product_id=product.id,
                quantity_ton=tender_quantity_ton(
                    Decimal(product.current_stock_kg),
                    Decimal(product.consumption_kg_per_min),
                    Decimal(product.target_coverage_minutes),
                ),
                status="OPEN",
                opened_at_seconds=now,
                offer_closes_at_seconds=now + Decimal(product.offer_window_seconds),
                evaluate_at_seconds=now + Decimal(product.offer_window_seconds) + Decimal("10"),
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
                    self.rng,
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
                        will_respond=plan.will_respond,
                        response_at_seconds=plan.response_at_seconds,
                        has_offer=False,
                        decision="PENDING",
                    )
                )
