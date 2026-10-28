import asyncio
from typing import List, Callable, Awaitable, Optional, Set
from flakeforge.scheduler.hooks import ScheduleTraceEntry
from flakeforge.scheduler.deterministic import run_coroutine_with_seed, DeterministicExecutionResult

class DeltaDebugMinimizer:
    """Minimizes the schedule trace to the smallest set of interleaving steps

    that deterministically triggers the bug (ddmin algorithm).
    """

    def __init__(self, coro_factory: Callable[[], Awaitable[None]], seed: int):
        self.coro_factory = coro_factory
        self.seed = seed

    async def minimize(self, full_trace: List[ScheduleTraceEntry]) -> List[ScheduleTraceEntry]:
        step_ids = [entry.step_id for entry in full_trace]
        if not step_ids:
            return full_trace

        minimal_steps = await self._ddmin(step_ids)
        step_set = set(minimal_steps)
        return [entry for entry in full_trace if entry.step_id in step_set]

    async def _test_subset(self, active_steps: Set[int]) -> bool:
        result: DeterministicExecutionResult = await run_coroutine_with_seed(
            coro_factory=self.coro_factory,
            seed=self.seed,
            active_steps=active_steps,
            timeout=2.0
        )
        # Returns True if it still reproduces the failure
        return not result.passed

    async def _ddmin(self, steps: List[int]) -> List[int]:
        n = 2
        current = list(steps)

        while len(current) >= 2:
            subsets = []
            chunk_size = max(1, len(current) // n)
            for i in range(0, len(current), chunk_size):
                subsets.append(current[i:i + chunk_size])

            reduced = False
            # 1. Try each chunk
            for subset in subsets:
                if await self._test_subset(set(subset)):
                    current = subset
                    n = 2
                    reduced = True
                    break

            if reduced:
                continue

            # 2. Try complements
            for subset in subsets:
                complement = [item for item in current if item not in set(subset)]
                if complement and await self._test_subset(set(complement)):
                    current = complement
                    n = max(n - 1, 2)
                    reduced = True
                    break

            if reduced:
                continue

            if n == len(current):
                break
            n = min(n * 2, len(current))

        return current
