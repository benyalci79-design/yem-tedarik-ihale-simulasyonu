from fastapi import APIRouter

from app.db import SessionLocal
from app.models import SimulationState
from app.runtime import engine

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


def serialize_state(state) -> dict:
    return {
        "is_running": bool(state.is_running),
        "elapsed_seconds": str(state.elapsed_seconds),
        "last_error": state.last_error,
    }


@router.get("")
def get_simulation() -> dict:
    with SessionLocal() as db:
        state = db.get(SimulationState, 1)
        if state is None:
            state = SimulationState(id=1, is_running=False, elapsed_seconds="0")
        return serialize_state(state)


@router.post("/start")
def start_simulation() -> dict:
    return serialize_state(engine.start())


@router.post("/pause")
def pause_simulation() -> dict:
    return serialize_state(engine.pause())
