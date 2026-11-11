from __future__ import annotations

import threading
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Protocol

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    Product,
    SimulationState,
    StockSnapshot,
    Tender,
    TenderAward,
    TenderParticipation,
)
from app.simulation.npc import DefaultRng, Rng, generate_offer, schedule_response
from app.simulation.rules import can_deliver_award, consume_stock, weighted_average_cost
from app.simulation.timeline import TimelineEvent, ordered_events

ACTIVE_STATUSES = ("OPEN", "EVALUATION", "AWARDED")
INCOMING_STATUSES = ("AWAITING_CARRIER", "IN_TRANSIT")
ZERO = Decimal("0")
THOUSANDTH = Decimal("0.001")
FOUR_PLACES = Decimal("0.0001")
# Zaman serisi grafiği için ürün başına tutulan en fazla nokta sayısı.
SNAPSHOT_RETENTION = 3000
SNAPSHOT_PRUNE_EVERY = 30


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
                if state is None:
                    state = SimulationState(id=1, is_running=False, elapsed_seconds=ZERO)
                    db.add(state)
                else:
                    state.is_running = False
                    state.last_tick_at = None
                return state

    def set_speed(self, speed: Decimal) -> SimulationState:
        """Önce eski hızla geçen zamanı işler, sonra hızı değiştirir.

        Böylece hız değişimi geçmiş zamanı yanlış ölçeklemez; sayaç, değişim
        anından itibaren yeni hızla ilerler. Simülasyon çalışmıyorsa başlatılır.
        """
        with self._lock:
            self.tick_once()
            with self.session_factory.begin() as db:
                state = db.get(SimulationState, 1, with_for_update=True)
                if state is None:
                    state = SimulationState(id=1, is_running=True, elapsed_seconds=ZERO)
                    db.add(state)
                state.speed_multiplier = speed
                state.is_running = True
                state.last_tick_at = self.clock.now()
                state.last_error = None
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

            real_delta = decimal_seconds((now - state.last_tick_at).total_seconds())
            speed = Decimal(state.speed_multiplier)
            delta = decimal_seconds(real_delta * speed)
            if delta <= ZERO:
                return state

            current = Decimal(state.elapsed_seconds)
            target = current + delta
            self._process_interval(db, current, target)
            state.elapsed_seconds = target
            state.last_tick_at = now
            state.last_error = None
            self._write_snapshots(db, target)
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

    def _consume_all(self, db, elapsed_seconds: Decimal) -> None:
        if elapsed_seconds <= ZERO:
            return
        for product in db.scalars(select(Product).order_by(Product.id)).all():
            # Tüketim yalnızca stoğu düşürür; ortalama birim maliyet değişmez.
            product.current_stock_kg = consume_stock(
                Decimal(product.current_stock_kg),
                Decimal(product.consumption_kg_per_min),
                elapsed_seconds,
            )

    def _events_between(self, db, current: Decimal, target: Decimal) -> list[tuple[Decimal, int, str, int]]:
        events: list[tuple[Decimal, int, str, int]] = []
        for award in db.scalars(
            select(TenderAward).where(
                TenderAward.status == "IN_TRANSIT",
                TenderAward.delivery_due_at_seconds.is_not(None),
            )
        ).all():
            due = Decimal(award.delivery_due_at_seconds)
            if current < due <= target:
                events.append((due, 0, "delivery", award.id))
        for tender in db.scalars(select(Tender).where(Tender.status == "OPEN").order_by(Tender.id)).all():
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
        return events

    def _process_event(self, db, kind: str, object_id: int, event_time: Decimal) -> None:
        if kind == "delivery":
            self._deliver_award(db, object_id, event_time)
        elif kind == "response":
            participation = db.get(TenderParticipation, object_id, with_for_update=True)
            if participation is not None:
                self._submit_offer(db, participation, event_time)
        elif kind == "close":
            tender = db.get(Tender, object_id, with_for_update=True)
            if tender is not None and tender.status == "OPEN":
                # Karar kullanıcıya aittir; motor burada durur.
                tender.status = "EVALUATION"

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
            Decimal(participation.min_available_kg),
            Decimal(participation.max_available_kg),
            self.rng,
        )
        participation.has_offer = True
        participation.unit_price = offer.unit_price
        participation.delivery_minutes = offer.delivery_minutes
        participation.offered_quantity_kg = offer.offered_quantity_kg
        participation.submitted_at_seconds = event_time
        participation.decision = "PENDING"

    def _deliver_award(self, db, award_id: int, event_time: Decimal) -> None:
        award = db.get(TenderAward, award_id, with_for_update=True)
        if award is None or not can_deliver_award(award.status, award.delivered_at_seconds):
            return
        tender = db.get(Tender, award.tender_id)
        if tender is None:
            return
        product = db.get(Product, tender.product_id, with_for_update=True)
        if product is None:
            return

        stock_before = Decimal(product.current_stock_kg)
        quantity = Decimal(award.quantity_kg)
        product.current_stock_kg = stock_before + quantity
        product.avg_cost_per_kg = weighted_average_cost(
            stock_before,
            Decimal(product.avg_cost_per_kg),
            quantity,
            Decimal(award.landed_cost_tl or ZERO),
        )
        award.delivered_at_seconds = event_time
        award.status = "DELIVERED"
        self._complete_tender_if_delivered(db, tender, event_time)
        self._write_snapshots(db, event_time)

    def _complete_tender_if_delivered(self, db, tender: Tender, event_time: Decimal) -> None:
        if tender.status != "AWARDED":
            return
        awards = tender.awards
        if awards and all(award.status == "DELIVERED" for award in awards):
            tender.status = "DELIVERED"
            tender.delivered_at_seconds = event_time

    def _write_snapshots(self, db, at_seconds: Decimal) -> None:
        """Tüm ürünler için aynı simülasyon anında tek satırlık anlık görüntü yazar."""
        exists = db.scalar(
            select(StockSnapshot.id).where(StockSnapshot.elapsed_seconds == at_seconds).limit(1)
        )
        if exists is not None:
            return
        for product in db.scalars(select(Product).order_by(Product.id)).all():
            stock = Decimal(product.current_stock_kg)
            avg_cost = Decimal(product.avg_cost_per_kg)
            db.add(
                StockSnapshot(
                    elapsed_seconds=at_seconds,
                    product_id=product.id,
                    stock_kg=stock,
                    avg_cost_per_kg=avg_cost,
                    value_tl=(stock * avg_cost).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
                )
            )
        db.flush()
        if int(at_seconds) % SNAPSHOT_PRUNE_EVERY == 0:
            self._prune_snapshots(db)

    def _prune_snapshots(self, db) -> None:
        """Ürün başına yaklaşık SNAPSHOT_RETENTION nokta kalacak şekilde eskileri siler.

        Tüm ürünler aynı anlarda yazıldığı için yaş eşiği ürün başına satır
        sayısını da sınırlar; her tick'te değil, seyrek çalışır.
        """
        threshold = db.scalar(
            select(StockSnapshot.elapsed_seconds)
            .group_by(StockSnapshot.elapsed_seconds)
            .order_by(StockSnapshot.elapsed_seconds.desc())
            .offset(SNAPSHOT_RETENTION - 1)
            .limit(1)
        )
        if threshold is not None:
            db.execute(delete(StockSnapshot).where(StockSnapshot.elapsed_seconds < threshold))
