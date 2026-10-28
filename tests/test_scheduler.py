import asyncio
import pytest
from flakeforge.scheduler.hooks import FlakeScheduler, __flake_yield__
from flakeforge.scheduler.deterministic import run_coroutine_with_seed

@pytest.mark.asyncio
async def test_flake_scheduler_records_trace():
    scheduler = FlakeScheduler.install(seed=123)
    await __flake_yield__("test_coro", 10)
    await __flake_yield__("test_coro", 20)
    FlakeScheduler.uninstall()

    assert len(scheduler.trace) == 2
    assert scheduler.trace[0].coro_name == "test_coro"
    assert scheduler.trace[0].line_no == 10

@pytest.mark.asyncio
async def test_deterministic_runner_passes():
    async def sample():
        await asyncio.sleep(0.001)

    res = await run_coroutine_with_seed(sample, seed=42)
    assert res.passed is True
