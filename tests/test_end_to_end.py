import pytest
from flakeforge.benchmarks.test_async_cache import run_cache_workload
from flakeforge.scheduler.deterministic import run_coroutine_with_seed
from flakeforge.verifier.stress_gate import StressGateVerifier

@pytest.mark.asyncio
async def test_end_to_end_concurrency_flake_detection():
    # Seeds 1 to 20 should encounter an intermittent cache state race
    found_flake = False
    for seed in range(1, 20):
        res = await run_coroutine_with_seed(run_cache_workload, seed=seed)
        if not res.passed:
            found_flake = True
            assert "AssertionError" in (res.error or "")
            break

    assert found_flake is True

@pytest.mark.asyncio
async def test_end_to_end_stress_gate_clean():
    async def clean_workload():
        pass

    gate = await StressGateVerifier.run_stress_gate(clean_workload, seed_count=100)
    assert gate["all_passed"] is True
    assert gate["passed"] == 100
