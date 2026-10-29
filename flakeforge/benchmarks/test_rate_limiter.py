import asyncio
import time
import pytest

class BuggyRateLimiter:
    """Sliding-window token rate limiter with concurrency leak."""

    def __init__(self, capacity: int = 3, refill_rate: float = 10.0):
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    async def acquire(self, amount: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * 10.0)
        self.last_refill = now

        # Classical check-then-act double-spend hazard:
        # Multiple concurrent requests see tokens >= amount BEFORE any task decrements!
        if self.tokens >= amount:
            await asyncio.sleep(0.001)  # Context switch window between check and deduction
            self.tokens -= amount
            return True
        return False

async def run_limiter_workload():
    limiter = BuggyRateLimiter(capacity=3)
    successful_grants = 0

    async def requester():
        nonlocal successful_grants
        if await limiter.acquire(1):
            successful_grants += 1

    # 10 burst requests when capacity is strictly 3
    tasks = [asyncio.create_task(requester()) for _ in range(10)]
    await asyncio.gather(*tasks)

    if successful_grants > 3:
        raise AssertionError(f"Rate limit breached! Permitted {successful_grants} requests (capacity: 3)")

@pytest.mark.asyncio
async def test_rate_limiter_race():
    await run_limiter_workload()