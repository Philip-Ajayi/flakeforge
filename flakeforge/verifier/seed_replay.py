from typing import Callable, Awaitable
from flakeforge.scheduler.deterministic import run_coroutine_with_seed, DeterministicExecutionResult

class SeedReplayer:
    """Proves reproducibility by verifying that the failing seed fails 100% of the time."""

    @staticmethod
    async def verify_failing_seed(
        coro_factory: Callable[[], Awaitable[None]],
        seed: int,
        reps: int = 5
    ) -> bool:
        for _ in range(reps):
            res: DeterministicExecutionResult = await run_coroutine_with_seed(coro_factory, seed=seed)
            if res.passed:
                return False  # Failed to reproduce consistently
        return True
