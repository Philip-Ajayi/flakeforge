import asyncio
import pytest

class BuggyBankAccount:
    """Asymmetric lock acquisition leading to dining philosophers deadlocks."""

    def __init__(self, account_id: str, balance: int):
        self.account_id = account_id
        self.balance = balance
        self.lock = asyncio.Lock()

    async def transfer(self, target: "BuggyBankAccount", amount: int) -> bool:
        # Non-ordered locking creates intermittent deadlock
        async with self.lock:
            await asyncio.sleep(0.001)
            async with target.lock:
                if self.balance >= amount:
                    self.balance -= amount
                    target.balance += amount
                    return True
                return False

async def run_bank_workload():
    acc_a = BuggyBankAccount("A", 1000)
    acc_b = BuggyBankAccount("B", 1000)

    # Cross-transfers
    t1 = asyncio.create_task(acc_a.transfer(acc_b, 100))
    t2 = asyncio.create_task(acc_b.transfer(acc_a, 200))

    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=0.5)

    if acc_a.balance + acc_b.balance != 2000:
        raise AssertionError("Conservation of funds violated!")

@pytest.mark.asyncio
async def test_bank_deadlock():
    await run_bank_workload()
