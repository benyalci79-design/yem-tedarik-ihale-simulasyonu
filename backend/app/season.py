from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import SimulationState

ZERO = Decimal("0")


def current_progress(db: Session) -> Decimal:
    state = db.get(SimulationState, 1)
    return Decimal(state.season_progress) if state is not None else ZERO
