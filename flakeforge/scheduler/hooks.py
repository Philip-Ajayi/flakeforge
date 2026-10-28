import asyncio
from typing import Optional, Dict, Any, List
from flakeforge.scheduler.seed import SeedSequence

class ScheduleTraceEntry:
    def __init__(self, task_name: str, coro_name: str, line_no: int, step_id: int):
        self.task_name = task_name
        self.coro_name = coro_name
        self.line_no = line_no
        self.step_id = step_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "coro_name": self.coro_name,
            "line_no": self.line_no,
            "step_id": self.step_id
        }

    def __repr__(self):
        return f"<TraceEntry step={self.step_id} task={self.task_name} coro={self.coro_name}:{self.line_no}>"

class FlakeScheduler:
    """Deterministic cooperative scheduler tracking and interleaving coroutine yields."""

    _instance: Optional["FlakeScheduler"] = None

    def __init__(self, seed: int = 42, active_steps: Optional[set] = None):
        self.seed = seed
        self.seed_seq = SeedSequence(seed)
        self.active_steps = active_steps  # Used by delta-minimizer to suppress non-minimal yields
        self.trace: List[ScheduleTraceEntry] = []
        self.step_counter = 0
        self.is_active = True

    @classmethod
    def get_current(cls) -> Optional["FlakeScheduler"]:
        return cls._instance

    @classmethod
    def install(cls, seed: int = 42, active_steps: Optional[set] = None) -> "FlakeScheduler":
        inst = cls(seed=seed, active_steps=active_steps)
        cls._instance = inst
        return inst

    @classmethod
    def uninstall(cls):
        cls._instance = None

    async def cooperative_yield(self, coro_name: str, line_no: int):
        """Called automatically by injected __flake_yield__ hooks."""
        if not self.is_active:
            return

        current_task = asyncio.current_task()
        task_name = current_task.get_name() if current_task else "main"

        self.step_counter += 1
        current_step = self.step_counter

        entry = ScheduleTraceEntry(
            task_name=task_name,
            coro_name=coro_name,
            line_no=line_no,
            step_id=current_step
        )
        self.trace.append(entry)

        # If a subset of active steps is designated (Delta Debugging), only yield if step in set
        if self.active_steps is not None and current_step not in self.active_steps:
            return

        if self.seed_seq.should_yield():
            delay = self.seed_seq.next_delay()
            await asyncio.sleep(delay)

async def __flake_yield__(coro_name: str = "", line_no: int = 0):
    """Runtime hook inserted by libcst into asynchronous AST yield boundaries."""
    scheduler = FlakeScheduler.get_current()
    if scheduler:
        await scheduler.cooperative_yield(coro_name, line_no)
    else:
        # Pass-through cooperative yield when no custom scheduler is installed
        await asyncio.sleep(0)
