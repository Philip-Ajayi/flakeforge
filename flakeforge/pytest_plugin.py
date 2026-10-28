import pytest
from flakeforge.scheduler.hooks import FlakeScheduler

def pytest_addoption(parser):
    group = parser.getgroup("flakeforge", "Deterministic Concurrency De-flaker")
    group.addoption(
        "--flake-seed",
        action="store",
        type=int,
        default=None,
        help="Replay a specific schedule permutation seed deterministically."
    )
    group.addoption(
        "--flake-stress",
        action="store",
        type=int,
        default=None,
        help="Run the test against N randomized seed permutations."
    )

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    seed = item.config.getoption("--flake-seed")
    if seed is not None:
        FlakeScheduler.install(seed=seed)

@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    FlakeScheduler.uninstall()
