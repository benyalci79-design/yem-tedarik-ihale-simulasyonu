from decimal import Decimal

from fastapi import APIRouter

from app.calendar import format_duration, format_short
from app.db import SessionLocal
from app.models import SimulationState
from app.runtime import engine
from app.schemas import SeasonRequest, SpeedRequest
from app.simulation.rules import season_label

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


def serialize_state(state) -> dict:
    progress = Decimal(state.season_progress) if state.season_progress is not None else Decimal("0")
    elapsed = Decimal(state.elapsed_seconds)
    return {
        "is_running": bool(state.is_running),
        "elapsed_seconds": str(state.elapsed_seconds),
        "elapsed_display": format_duration(elapsed),
        "elapsed_short": format_short(elapsed),
        "speed": str(state.speed_multiplier),
        "season_progress": str(progress),
        "season_label": season_label(progress),
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


@router.post("/speed")
def set_simulation_speed(payload: SpeedRequest) -> dict:
    return serialize_state(engine.set_speed(Decimal(payload.speed)))


@router.post("/reset")
def reset_simulation() -> dict:
    return serialize_state(engine.reset())


@router.post("/season")
def set_season(payload: SeasonRequest) -> dict:
    return serialize_state(engine.set_season_progress(payload.progress))
