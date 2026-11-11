from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from random import Random
from typing import Protocol


class Rng(Protocol):
    def random(self) -> float: ...
    def randint(self, start: int, end: int) -> int: ...


@dataclass(frozen=True)
class OfferPlan:
    will_respond: bool
    response_at_seconds: Decimal | None


@dataclass(frozen=True)
class GeneratedOffer:
    unit_price: Decimal
    delivery_minutes: int


def schedule_response(
    opened_at_seconds: Decimal,
    closes_at_seconds: Decimal,
    response_probability: Decimal,
    rng: Rng,
) -> OfferPlan:
    """Cevap planını açılış/kapanış sınırlarını ihlal etmeden tek kez üretir.

    Simülasyon anları milisaniye hassasiyetinde tutulduğu için ``int`` ile
    aşağı yuvarlamak, örneğin 12.750. saniyede açılan bir ihaleye 13.000.
    saniyede (yalnızca 0.250 saniye sonra) cevap planlanmasına yol açardı.
    RNG aralığı milisaniye tamsayılarıyla çalıştırılarak alt/üst sınırlar
    açılıştan tam 1 saniye sonrası ve kapanıştan tam 1 saniye öncesi olur.
    """
    will_respond = rng.random() < float(response_probability)
    if not will_respond:
        return OfferPlan(False, None)
    scale = Decimal("1000")
    first = int((opened_at_seconds * scale).to_integral_value(rounding=ROUND_CEILING)) + 1000
    last = int((closes_at_seconds * scale).to_integral_value(rounding=ROUND_FLOOR)) - 1000
    if first > last:
        return OfferPlan(False, None)
    return OfferPlan(True, (Decimal(rng.randint(first, last)) / scale).quantize(Decimal("0.001")))


def generate_offer(
    min_price: Decimal,
    max_price: Decimal,
    min_delivery_minutes: int,
    max_delivery_minutes: int,
    rng: Rng,
) -> GeneratedOffer:
    min_cents = int(min_price * 100)
    max_cents = int(max_price * 100)
    return GeneratedOffer(
        unit_price=Decimal(rng.randint(min_cents, max_cents)) / Decimal("100"),
        delivery_minutes=rng.randint(min_delivery_minutes, max_delivery_minutes),
    )


class DefaultRng(Random):
    """Production'da sabit seed kullanılmaz; testler bu bağımlılığı enjekte eder."""
