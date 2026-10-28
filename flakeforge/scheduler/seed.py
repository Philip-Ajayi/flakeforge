import random
from typing import List

class SeedSequence:
    """Generates and manages deterministic permutations and random schedule choices."""

    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)

    def next_delay(self) -> float:
        """Returns a microsecond cooperative delay factor."""
        # Yields deterministic microscopic sleep bounds between 0.0001 and 0.005 seconds
        return self.rng.choice([0.0001, 0.0005, 0.001, 0.002, 0.005])

    def should_yield(self) -> bool:
        """Determines if a cooperative schedule boundary should actively yield."""
        return self.rng.random() > 0.35

    def permute_order(self, items: List[any]) -> List[any]:
        """Returns a deterministic shuffled view of runnable tasks."""
        copy_items = list(items)
        self.rng.shuffle(copy_items)
        return copy_items
