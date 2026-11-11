from decimal import Decimal

SECONDS_PER_DAY = 30
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
SECONDS_PER_MONTH = SECONDS_PER_DAY * DAYS_PER_MONTH
SECONDS_PER_YEAR = SECONDS_PER_MONTH * MONTHS_PER_YEAR

ZERO = Decimal("0")


def split_duration(seconds: Decimal) -> dict:
    total = Decimal(seconds)
    if total < ZERO:
        total = ZERO
    years = int(total // SECONDS_PER_YEAR)
    remainder = total - Decimal(years * SECONDS_PER_YEAR)
    months = int(remainder // SECONDS_PER_MONTH)
    remainder -= Decimal(months * SECONDS_PER_MONTH)
    days = int(remainder // SECONDS_PER_DAY)
    remainder -= Decimal(days * SECONDS_PER_DAY)

    day_fraction = float(remainder) / SECONDS_PER_DAY
    hours = int(day_fraction * 24)
    minutes = int((day_fraction * 24 - hours) * 60)
    secs = int(((day_fraction * 24 - hours) * 60 - minutes) * 60)
    return {
        "years": years,
        "months": months,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": secs,
    }


def _date_part(parts: dict) -> str:
    chunks: list[str] = []
    if parts["years"]:
        chunks.append(f"{parts['years']} yıl")
    if parts["months"]:
        chunks.append(f"{parts['months']} ay")
    if parts["days"] or not chunks:
        chunks.append(f"{parts['days']} gün")
    return " ".join(chunks)


def format_duration(seconds: Decimal) -> str:
    parts = split_duration(seconds)
    return (
        f"{_date_part(parts)} "
        f"{parts['hours']:02d}:{parts['minutes']:02d}:{parts['seconds']:02d}"
    )


def format_short(seconds: Decimal) -> str:
    parts = split_duration(seconds)
    return f"{_date_part(parts)} {parts['hours']:02d}:{parts['minutes']:02d}"
