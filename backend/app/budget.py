from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, SimulationState, TenderAward
from app.simulation.rules import TON_KG

BUDGET_PERIOD_SECONDS = Decimal("3600")
DEFAULT_LIMIT_TL = Decimal("500000.00")
ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")


def elapsed_seconds(db: Session) -> Decimal:
    state = db.get(SimulationState, 1)
    return Decimal(state.elapsed_seconds) if state is not None else ZERO


def period_start(elapsed: Decimal) -> Decimal:
    return (elapsed // BUDGET_PERIOD_SECONDS) * BUDGET_PERIOD_SECONDS


def period_index(elapsed: Decimal) -> int:
    return int(elapsed // BUDGET_PERIOD_SECONDS) + 1


def award_cost(award: TenderAward) -> Decimal:
    """Award'ın bütçeye yazılan maliyeti; nakliye bilinmiyorsa mal bedeli."""
    if award.landed_cost_tl is not None:
        return Decimal(award.landed_cost_tl)
    return (Decimal(award.quantity_kg) / TON_KG * Decimal(award.unit_price_per_ton)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )


def spent_in_period(db: Session, start: Decimal) -> Decimal:
    awards = db.scalars(
        select(TenderAward).where(TenderAward.accepted_at_seconds >= start)
    ).all()
    total = sum((award_cost(award) for award in awards), ZERO)
    return total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def budget_state(db: Session) -> dict:
    budget = db.get(Budget, 1)
    limit = Decimal(budget.monthly_limit_tl) if budget is not None else DEFAULT_LIMIT_TL
    elapsed = elapsed_seconds(db)
    start = period_start(elapsed)
    spent = spent_in_period(db, start)
    remaining = max(ZERO, limit - spent)
    usage = ((spent / limit) * Decimal("100")).quantize(TWO_PLACES) if limit > ZERO else ZERO
    return {
        "monthly_limit_tl": str(limit),
        "spent_tl": str(spent),
        "remaining_tl": str(remaining),
        "usage_percent": str(usage),
        "period_index": period_index(elapsed),
        "period_start_seconds": str(start),
        "period_end_seconds": str(start + BUDGET_PERIOD_SECONDS),
        "exceeded": spent >= limit,
    }
