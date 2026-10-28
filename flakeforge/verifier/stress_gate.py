import asyncio
from typing import Callable, Awaitable, Dict, Any
from flakeforge.scheduler.deterministic import run_coroutine_with_seed

class StressGateVerifier:
    """Executes N randomized seed permutations against the synthesized patch

    to rigorously guarantee absence of race conditions, deadlocks, and timeouts.
    """

    @staticmethod
    async def run_stress_gate(
        coro_factory: Callable[[], Awaitable[None]],
        seed_count: int = 1000,
        start_seed: int = 10000,
        progress_callback: any = None
    ) -> Dict[str, Any]:
        passed_count = 0
        failed_count = 0
        failures = []

        start_time = asyncio.get_event_loop().time()

        for i in range(seed_count):
            current_seed = start_seed + i
            res = await run_coroutine_with_seed(
                coro_factory=coro_factory,
                seed=current_seed,
                timeout=2.0
            )
            if res.passed:
                passed_count += 1
            else:
                failed_count += 1
                failures.append({
                    "seed": current_seed,
                    "error": res.error
                })
                # Fast fail if deadlock or flakiness remains
                break

            if progress_callback and (i + 1) % 50 == 0:
                progress_callback(i + 1, seed_count)

        total_time = asyncio.get_event_loop().time() - start_time

        return {
            "total_tested": passed_count + failed_count,
            "passed": passed_count,
            "failed": failed_count,
            "all_passed": failed_count == 0,
            "duration_seconds": round(total_time, 3),
            "failures": failures
        }
