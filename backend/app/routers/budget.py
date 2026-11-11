from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.budget import DEFAULT_LIMIT_TL, budget_state
from app.db import get_db
from app.errors import ApiError
from app.models import Budget, SimulationState
from app.schemas import BudgetPatch

router = APIRouter(prefix="/api/v1/budget", tags=["budget"])


@router.get("")
def get_budget(db: Session = Depends(get_db)) -> dict:
    return budget_state(db)


@router.patch("")
def update_budget(payload: BudgetPatch, db: Session = Depends(get_db)) -> dict:
    state = db.get(SimulationState, 1, with_for_update=True)
    if state is not None and state.is_running:
        raise ApiError(409, "SETTINGS_LOCKED", "Simülasyon çalışırken bütçe değiştirilemez.")
    budget = db.get(Budget, 1, with_for_update=True)
    if budget is None:
        budget = Budget(
            id=1,
            code="YEM-HAM",
            name="Yem Hammadde Bütçesi",
            monthly_limit_tl=DEFAULT_LIMIT_TL,
            is_active=True,
        )
        db.add(budget)
    budget.monthly_limit_tl = payload.monthly_limit_tl
    db.commit()
    return budget_state(db)
