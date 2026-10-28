import asyncio
import pytest

class TaskLeakService:
    def __init__(self):
        self.active_workers = 0

    async def background_worker(self):
        self.active_workers += 1
        try:
            await asyncio.sleep(10)
        finally:
            self.active_workers -= 1

    async def handle_request(self, fail_fast: bool = True):
        # Spawns unstructured detached task
        asyncio.create_task(self.background_worker())
        await asyncio.sleep(0.001)
        if fail_fast:
            raise RuntimeError("Request handling failed unexpectedly")

async def run_leak_workload():
    svc = TaskLeakService()
    try:
        await svc.handle_request(fail_fast=True)
    except RuntimeError:
        pass

    # Wait brief moment for cancellation propagation
    await asyncio.sleep(0.01)
    if svc.active_workers > 0:
        raise AssertionError(f"Leaked {svc.active_workers} orphaned background task(s)!")

@pytest.mark.asyncio
async def test_task_group_leak():
    await run_leak_workload()
