import asyncio
from contextlib import suppress

from app.simulation.engine import SimulationEngine

engine = SimulationEngine()


async def simulation_loop() -> None:
    while True:
        await asyncio.to_thread(engine.tick_once)
        await asyncio.sleep(1)


async def start_runtime() -> asyncio.Task:
    engine.initialize_after_restart()
    return asyncio.create_task(simulation_loop())


async def stop_runtime(task: asyncio.Task) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
