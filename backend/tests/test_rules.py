from decimal import Decimal

from app.simulation.evaluation import CandidateOffer, evaluate_offers
from app.simulation.npc import generate_offer, schedule_response
from app.simulation.rules import (
    consume_stock,
    coverage_minutes,
    deliver_stock_once,
    round_up_ton,
    tender_quantity_ton,
)
from app.simulation.timeline import TimelineEvent, ordered_events


class FixedRng:
    def __init__(self, random_value: float = 0.0, integers: list[int] | None = None):
        self.random_value = random_value
        self.integers = iter(integers or [])

    def random(self) -> float:
        return self.random_value

    def randint(self, _start: int, _end: int) -> int:
        return next(self.integers)


class CapturingRng(FixedRng):
    def __init__(self, integers: list[int]):
        super().__init__(random_value=0.0, integers=integers)
        self.bounds: tuple[int, int] | None = None

    def randint(self, start: int, end: int) -> int:
        self.bounds = (start, end)
        return super().randint(start, end)


def test_consumption_never_makes_stock_negative():
    assert consume_stock(Decimal("10"), Decimal("100"), Decimal("60")) == Decimal("0")


def test_consumption_and_coverage():
    stock = consume_stock(Decimal("900"), Decimal("100"), Decimal("60"))
    assert stock == Decimal("800")
    assert coverage_minutes(stock, Decimal("100")) == Decimal("8")


def test_quantity_is_rounded_up_to_thousandth_ton():
    assert tender_quantity_ton(Decimal("900"), Decimal("100"), Decimal("30")) == Decimal("2.100")
    assert round_up_ton(Decimal("1000.001")) == Decimal("1.001")


def test_probability_boundaries():
    assert schedule_response(Decimal("0"), Decimal("60"), Decimal("0"), FixedRng(0.0)).will_respond is False
    assert schedule_response(Decimal("0"), Decimal("60"), Decimal("1"), FixedRng(0.999, [10])).will_respond is True


def test_response_window_respects_decimal_opening_and_closing_boundaries():
    rng = CapturingRng([13750])
    plan = schedule_response(Decimal("12.750"), Decimal("72.750"), Decimal("1"), rng)
    assert rng.bounds == (13750, 71750)
    assert plan.response_at_seconds == Decimal("13.750")


def test_offer_price_and_delivery_are_inclusive():
    offer = generate_offer(
        Decimal("8000.00"), Decimal("9500.00"), 1, 3, FixedRng(integers=[800000, 3])
    )
    assert offer.unit_price == Decimal("8000")
    assert offer.delivery_minutes == 3


def test_eligible_offer_beats_cheaper_late_offer():
    result = evaluate_offers(
        [
            CandidateOffer(1, 2, Decimal("8000"), 3),
            CandidateOffer(2, 1, Decimal("7000"), 8),
        ],
        Decimal("3.5"),
    )
    assert result.winner_id == 1
    assert result.rejected_reasons[2] == "Stok bitmeden teslim edemiyor"


def test_emergency_acceptance():
    result = evaluate_offers(
        [
            CandidateOffer(1, 2, Decimal("8000"), 5),
            CandidateOffer(2, 1, Decimal("7000"), 3),
        ],
        Decimal("2"),
    )
    assert result.winner_id == 2
    assert result.accepted_reason == "Gecikmeli teslim riskiyle acil kabul"


def test_equal_boundary_is_eligible():
    result = evaluate_offers([CandidateOffer(1, 1, Decimal("8000"), 3)], Decimal("3.5"))
    assert result.winner_id == 1


def test_delivery_is_idempotent():
    stock, status, changed = deliver_stock_once("AWARDED", None, Decimal("0"), Decimal("2.100"))
    assert (stock, status, changed) == (Decimal("2100.000"), "DELIVERED", True)
    assert deliver_stock_once("DELIVERED", Decimal("10"), stock, Decimal("2.100")) == (stock, "DELIVERED", False)


def test_long_tick_event_order_is_chronological_and_prioritized():
    ordered = ordered_events([
        TimelineEvent(Decimal("20"), "evaluate", 1),
        TimelineEvent(Decimal("10"), "close", 1),
        TimelineEvent(Decimal("10"), "delivery", 2),
        TimelineEvent(Decimal("10"), "response", 4),
    ])
    assert [(event.at_seconds, event.kind) for event in ordered] == [
        (Decimal("10"), "delivery"),
        (Decimal("10"), "response"),
        (Decimal("10"), "close"),
        (Decimal("20"), "evaluate"),
    ]
