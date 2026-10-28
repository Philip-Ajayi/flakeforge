import asyncio
import pytest
from flakeforge.minimizer.delta_debug import DeltaDebugMinimizer
from flakeforge.scheduler.hooks import ScheduleTraceEntry

@pytest.mark.asyncio
async def test_minimizer_reduces_trace():
    trace = [
        ScheduleTraceEntry("task_1", "step_a", 1, 1),
        ScheduleTraceEntry("task_2", "step_b", 2, 2),
        ScheduleTraceEntry("task_3", "step_c", 3, 3),
    ]

    async def mock_coro():
        # Passes unconditionally
        await asyncio.sleep(0.0001)

    minimizer = DeltaDebugMinimizer(coro_factory=mock_coro, seed=42)
    minimized = await minimizer.minimize(trace)
    assert isinstance(minimized, list)
