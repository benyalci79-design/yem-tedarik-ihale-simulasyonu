from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

ZERO = Decimal("0")
TON_KG = Decimal("1000")
THOUSANDTH_TON = Decimal("0.001")
SIX_PLACES = Decimal("0.000001")
TWO_PLACES = Decimal("0.01")
MILLISECOND = Decimal("0.001")
SEASON_PERIOD_SECONDS = Decimal("3600")


def consumed_kg(consumption_kg_per_min: Decimal, elapsed_seconds: Decimal) -> Decimal:
    """Dakikalık tüketimi simülasyon saniyesine çevirir."""
    return consumption_kg_per_min * elapsed_seconds / Decimal("60")


def consume_stock(stock_kg: Decimal, consumption_kg_per_min: Decimal, elapsed_seconds: Decimal) -> Decimal:
    """Stok negatif olamaz; tüketim tek bir olay aralığı için uygulanır."""
    return max(ZERO, stock_kg - consumed_kg(consumption_kg_per_min, elapsed_seconds))


def coverage_minutes(stock_kg: Decimal, consumption_kg_per_min: Decimal) -> Decimal:
    if consumption_kg_per_min <= ZERO:
        raise ValueError("Tüketim sıfırdan büyük olmalıdır.")
    return stock_kg / consumption_kg_per_min


def round_up_ton(quantity_kg: Decimal) -> Decimal:
    """Alım miktarını şartnamedeki 0,001 ton basamağına yukarı yuvarlar."""
    if quantity_kg <= ZERO:
        return ZERO
    units = (quantity_kg / TON_KG / THOUSANDTH_TON).to_integral_value(rounding=ROUND_CEILING)
    return (units * THOUSANDTH_TON).quantize(THOUSANDTH_TON)


def tender_quantity_ton(
    stock_kg: Decimal,
    consumption_kg_per_min: Decimal,
    target_coverage_minutes: Decimal,
) -> Decimal:
    target_stock_kg = target_coverage_minutes * consumption_kg_per_min
    return round_up_ton(max(ZERO, target_stock_kg - stock_kg))


def price_per_ton_to_per_kg(price_per_ton: Decimal) -> Decimal:
    """TL/ton fiyatı TL/kg birimine çevirir (tek dönüşüm noktası)."""
    return (price_per_ton / TON_KG).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)


def free_capacity_kg(capacity_kg: Decimal, stock_kg: Decimal, incoming_kg: Decimal) -> Decimal:
    """Boş depo kapasitesi: yoldaki (teslim edilmemiş) miktarlar da yeri işgal eder."""
    return max(ZERO, capacity_kg - stock_kg - incoming_kg)


def check_capacity(capacity_kg: Decimal, stock_kg: Decimal, incoming_kg: Decimal, added_kg: Decimal) -> bool:
    """Eklenecek miktar boş kapasiteyi aşıyorsa False döner."""
    return added_kg <= free_capacity_kg(capacity_kg, stock_kg, incoming_kg)


def remaining_need_kg(tender_quantity_ton_value: Decimal, accepted_total_kg: Decimal) -> Decimal:
    """İhalenin henüz kabul edilmemiş miktarı (kg)."""
    return max(ZERO, tender_quantity_ton_value * TON_KG - accepted_total_kg)


def max_acceptable_kg(offered_kg: Decimal, remaining_need_kg_value: Decimal, free_capacity_kg_value: Decimal) -> Decimal:
    """Bir tekliften kabul edilebilecek en yüksek miktar; üç sınırın minimumu."""
    return max(ZERO, min(offered_kg, remaining_need_kg_value, free_capacity_kg_value))


def landed_cost_tl(
    quantity_kg: Decimal,
    unit_price_per_ton: Decimal,
    carrier_price_per_ton: Decimal | None,
) -> Decimal:
    """Teslim edilen miktarın toplam maliyeti: (mal + nakliye) TL/ton üzerinden."""
    freight = carrier_price_per_ton or ZERO
    return (quantity_kg / TON_KG * (unit_price_per_ton + freight)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def weighted_average_cost(
    stock_kg: Decimal,
    avg_cost_per_kg: Decimal,
    added_kg: Decimal,
    added_total_cost_tl: Decimal,
) -> Decimal:
    """Teslimattan sonra stoktaki ürünün ağırlıklı ortalama birim maliyeti.

    Tüketim ortalama maliyeti değiştirmez; bu fonksiyon yalnızca stok eklenirken
    çağrılır. Toplam miktar sıfırsa (stok ve eklenen miktar yoksa) son bilinen
    birim maliyet korunur; böylece stok bitince fiyat 0'a düşmez.
    """
    total_kg = stock_kg + added_kg
    if total_kg <= ZERO:
        return avg_cost_per_kg
    total_value = stock_kg * avg_cost_per_kg + added_total_cost_tl
    return (total_value / total_kg).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)


def delivery_due_seconds(
    accepted_at_seconds: Decimal,
    prep_minutes: int,
    carrier_assigned_at_seconds: Decimal | None,
    transit_minutes: int | None,
) -> Decimal:
    """Teslim anı: hazırlık süresi + (nakliye hariçse) taşıma süresi.

    Nakliye dahil tekliflerde mal, hazırlık süresi sonunda teslim edilmiş sayılır.
    Hariç tekliflerde hazırlık ve nakliyeci ataması paralel yürür; teslim, ikisinin
    geç biteni ile taşıma süresinin toplamıdır.
    """
    ready_at = accepted_at_seconds + Decimal(prep_minutes) * Decimal("60")
    if transit_minutes is None:
        return ready_at.quantize(MILLISECOND, rounding=ROUND_HALF_UP)
    start_at = max(ready_at, carrier_assigned_at_seconds or ready_at)
    return (start_at + Decimal(transit_minutes) * Decimal("60")).quantize(
        MILLISECOND, rounding=ROUND_HALF_UP
    )


def can_deliver_award(status: str, delivered_at_seconds: Decimal | None) -> bool:
    """Teslimat yalnızca yoldaki ve henüz teslim edilmemiş award için uygulanır.

    Motor bu koşulu teslimat olayını işlemeden önce kontrol eder; böylece aynı
    award için stok ve maliyet ikinci kez eklenmez (idempotent teslimat).
    """
    return status == "IN_TRANSIT" and delivered_at_seconds is None


def apply_loss(quantity_kg: Decimal, loss_percent: Decimal) -> Decimal:
    """Mal kabulde fire düşülmüş net miktar (kg)."""
    if loss_percent <= ZERO:
        return quantity_kg
    safe_percent = min(loss_percent, Decimal("100"))
    return (quantity_kg * (Decimal("100") - safe_percent) / Decimal("100")).quantize(
        SIX_PLACES, rounding=ROUND_HALF_UP
    )


def season_phase(product_id: int) -> float:
    """Ürünlere dengeli dağılmış mevsim fazı (radyan)."""
    import math

    return (product_id % 3) * (2 * math.pi / 3)


def season_factor(
    elapsed_seconds: Decimal,
    amplitude_percent: Decimal,
    phase_radians: float,
) -> Decimal:
    """Mevsimsel fiyat katsayısı: 1 + genlik * sin(2π t / periyot + faz)."""
    import math

    if amplitude_percent <= ZERO:
        return Decimal("1")
    angle = 2 * math.pi * float(elapsed_seconds) / float(SEASON_PERIOD_SECONDS) + phase_radians
    factor = Decimal("1") + (amplitude_percent / Decimal("100")) * Decimal(str(math.sin(angle)))
    return factor.quantize(SIX_PLACES, rounding=ROUND_HALF_UP)
