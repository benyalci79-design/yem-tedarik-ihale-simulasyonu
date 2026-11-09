from decimal import Decimal

from app.simulation.evaluation import CandidateOffer, evaluate_offers
from app.simulation.npc import generate_offer, schedule_response
from app.simulation.rules import (
    consume_stock,
    coverage_minutes,
    round_up_ton,
    tender_quantity_ton,
)


class FixedRng:
    def __init__(self, random_value: float = 0.0, integers: list[int] | None = None):
        self.random_value = random_value
        self.integers = iter(integers or [])

    def random(self) -> float:
        return self.random_value

    def randint(self, _start: int, _end: int) -> int:
        return next(self.integers)


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
