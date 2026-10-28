import asyncio
import pytest

class BuggyAsyncCache:
    """An asynchronous cache with an unshielded read-after-write hazard."""

    def __init__(self):
        self._store = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: any):
        await asyncio.sleep(0.001)  # Micro I/O latency
        self._store[key] = value

    async def update_counter(self, key: str, delta: int = 1):
        # Read-after-write race condition
        val = self._store.get(key, 0)
        await asyncio.sleep(0.001)  # Cooperative yield window
        self._store[key] = val + delta
        return self._store[key]

async def run_cache_workload():
    cache = BuggyAsyncCache()
    await cache.set("counter", 0)

    # 5 concurrent tasks updating the counter simultaneously
    async def worker():
        for _ in range(5):
            await cache.update_counter("counter", 1)

    tasks = [asyncio.create_task(worker()) for _ in range(5)]
    await asyncio.gather(*tasks)

    final_val = await cache.get("counter")
    # Expected: 5 tasks * 5 increments = 25
    if final_val != 25:
        raise AssertionError(f"Cache state out of sync! Expected 25, got {final_val}")

@pytest.mark.asyncio
async def test_async_cache_race():
    await run_cache_workload()
