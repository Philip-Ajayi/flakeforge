import asyncio
from typing import Tuple, List, Optional
from flakeforge.scheduler.hooks import FlakeScheduler, ScheduleTraceEntry

class DeterministicExecutionResult:
    def __init__(
        self,
        seed: int,
        passed: bool,
        error: Optional[str] = None,
        trace: Optional[List[ScheduleTraceEntry]] = None,
        duration: float = 0.0
    ):
        self.seed = seed
        self.passed = passed
        self.error = error
        self.trace = trace or []
        self.duration = duration

    def to_dict(self):
        return {
            "seed": self.seed,
            "passed": self.passed,
            "error": self.error,
            "trace": [t.to_dict() for t in self.trace],
            "duration": self.duration
        }

async def run_coroutine_with_seed(
    coro_factory,
    seed: int,
    active_steps: Optional[set] = None,
    timeout: float = 3.0
) -> DeterministicExecutionResult:
    """Executes a coroutine under the control of FlakeScheduler at a specific seed."""
    scheduler = FlakeScheduler.install(seed=seed, active_steps=active_steps)
    start_time = asyncio.get_event_loop().time()
    try:
        coro = coro_factory()
        await asyncio.wait_for(coro, timeout=timeout)
        duration = asyncio.get_event_loop().time() - start_time
        trace_copy = list(scheduler.trace)
        FlakeScheduler.uninstall()
        return DeterministicExecutionResult(
            seed=seed,
            passed=True,
            trace=trace_copy,
            duration=duration
        )
    except Exception as exc:
        duration = asyncio.get_event_loop().time() - start_time
        trace_copy = list(scheduler.trace)
        FlakeScheduler.uninstall()
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        return DeterministicExecutionResult(
            seed=seed,
            passed=False,
            error=error_msg,
            trace=trace_copy,
            duration=duration
        )
    finally:
        FlakeScheduler.uninstall()
