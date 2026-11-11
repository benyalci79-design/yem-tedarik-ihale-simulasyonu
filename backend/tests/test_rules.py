from decimal import Decimal

import pytest

from app.routers.metrics import _last_known_avg
from app.simulation.npc import generate_offer, schedule_response
from app.simulation.rules import (
    can_deliver_award,
    check_capacity,
    consume_stock,
    coverage_minutes,
    delivery_due_seconds,
    free_capacity_kg,
    landed_cost_tl,
    max_acceptable_kg,
    price_per_ton_to_per_kg,
    remaining_need_kg,
    round_up_ton,
    tender_quantity_ton,
    weighted_average_cost,
)
from app.simulation.timeline import TimelineEvent, ordered_events
from app.schemas import NpcRulePatch, ProductPatch, SpeedRequest, TenderAccept, TenderCreate


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


def test_consumption_does_not_change_unit_cost():
    stock = consume_stock(Decimal("900"), Decimal("100"), Decimal("60"))
    assert (stock * Decimal("8.750000")).quantize(Decimal("0.0001")) == Decimal("7000.0000")


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


def test_offer_price_delivery_and_quantity_are_inclusive():
    offer = generate_offer(
        Decimal("8000.00"),
        Decimal("9500.00"),
        1,
        3,
        Decimal("1000"),
        Decimal("3000"),
        FixedRng(integers=[800000, 3, 2500]),
    )
    assert offer.unit_price == Decimal("8000")
    assert offer.delivery_minutes == 3
    assert offer.offered_quantity_kg == Decimal("2500")


def test_price_per_ton_to_per_kg():
    assert price_per_ton_to_per_kg(Decimal("8750")) == Decimal("8.750000")


def test_free_capacity_accounts_for_stock_and_incoming():
    assert free_capacity_kg(Decimal("5000"), Decimal("900"), Decimal("1000")) == Decimal("3100")
    assert free_capacity_kg(Decimal("1000"), Decimal("900"), Decimal("500")) == Decimal("0")


def test_capacity_boundary_is_inclusive():
    assert check_capacity(Decimal("5000"), Decimal("1000"), Decimal("500"), Decimal("3500")) is True
    assert check_capacity(Decimal("5000"), Decimal("1000"), Decimal("500"), Decimal("3500.001")) is False


def test_remaining_need_and_max_acceptable_quantity():
    remaining = remaining_need_kg(Decimal("3"), Decimal("500"))
    assert remaining == Decimal("2500")
    assert remaining_need_kg(Decimal("3"), Decimal("4000")) == Decimal("0")
    assert max_acceptable_kg(Decimal("2000"), remaining, Decimal("900")) == Decimal("900")


def test_landed_cost_with_and_without_freight():
    assert landed_cost_tl(Decimal("2000"), Decimal("8000"), None) == Decimal("16000.00")
    assert landed_cost_tl(Decimal("2000"), Decimal("8000"), Decimal("500")) == Decimal("17000.00")


def test_weighted_average_cost():
    assert weighted_average_cost(Decimal("0"), Decimal("0"), Decimal("2000"), Decimal("16000")) == Decimal(
        "8.000000"
    )
    assert weighted_average_cost(Decimal("1000"), Decimal("8"), Decimal("1000"), Decimal("9000")) == Decimal(
        "8.500000"
    )
    assert weighted_average_cost(Decimal("0"), Decimal("9.5"), Decimal("0"), Decimal("0")) == Decimal("9.5")
    assert weighted_average_cost(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")) == Decimal("0")


def test_delivery_due_with_freight_included():
    assert delivery_due_seconds(Decimal("100"), 2, None, None) == Decimal("220.000")


def test_delivery_due_with_carrier_waits_for_assignment():
    assert delivery_due_seconds(Decimal("100"), 1, Decimal("300"), 2) == Decimal("420.000")
    assert delivery_due_seconds(Decimal("100"), 5, Decimal("150"), 2) == Decimal("520.000")


def test_total_unit_price_is_preserved_when_stock_is_zero():
    assert _last_known_avg([Decimal("8"), Decimal("10")]) == Decimal("9.000000")
    assert _last_known_avg([]) == Decimal("0")


def test_award_delivery_is_idempotent():
    assert can_deliver_award("IN_TRANSIT", None) is True
    assert can_deliver_award("DELIVERED", Decimal("10")) is False
    assert can_deliver_award("AWAITING_CARRIER", None) is False


def test_long_tick_event_order_is_chronological_and_prioritized():
    ordered = ordered_events([
        TimelineEvent(Decimal("20"), "close", 1),
        TimelineEvent(Decimal("10"), "close", 1),
        TimelineEvent(Decimal("10"), "delivery", 2),
        TimelineEvent(Decimal("10"), "response", 4),
    ])
    assert [(event.at_seconds, event.kind) for event in ordered] == [
        (Decimal("10"), "delivery"),
        (Decimal("10"), "response"),
        (Decimal("10"), "close"),
        (Decimal("20"), "close"),
    ]


def test_patch_schemas_reject_null_and_excess_precision():
    with pytest.raises(ValueError):
        ProductPatch(current_stock_kg=None)
    with pytest.raises(ValueError):
        ProductPatch(current_stock_kg=Decimal("1.1234"))
    with pytest.raises(ValueError):
        ProductPatch(capacity_kg=Decimal("5000.0001"))
    with pytest.raises(ValueError):
        NpcRulePatch(min_price=None)
    with pytest.raises(ValueError):
        NpcRulePatch(min_available_kg=Decimal("1200"), max_available_kg=Decimal("1000"))


def test_tender_and_speed_payload_validation():
    with pytest.raises(ValueError):
        TenderCreate(product_id=1, quantity_ton=Decimal("1.2345"))
    with pytest.raises(ValueError):
        TenderAccept(participation_id=1, quantity_kg=Decimal("0"))
    assert TenderCreate(product_id=1, quantity_ton=Decimal("2.100")).quantity_ton == Decimal("2.100")
    assert SpeedRequest(speed="0.5").speed == "0.5"
    with pytest.raises(ValueError):
        SpeedRequest(speed="4")
