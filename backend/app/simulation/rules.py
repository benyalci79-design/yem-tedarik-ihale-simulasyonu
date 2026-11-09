from decimal import Decimal, ROUND_CEILING

ZERO = Decimal("0")
TON_KG = Decimal("1000")
THOUSANDTH_TON = Decimal("0.001")


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
