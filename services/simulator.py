"""Vectorized Monte Carlo production simulation."""

from dataclasses import dataclass

import numpy as np


@dataclass
class ProductionSimulator:
    """Independent binomial production simulator."""

    probability: float
    quantity: int
    iterations: int
    seed: int | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.probability <= 1:
            raise ValueError("概率必须在 0 和 1 之间")
        if self.quantity <= 0 or self.iterations <= 0:
            raise ValueError("数量和迭代次数必须大于 0")

    def _rng(self) -> np.random.Generator:
        return np.random.default_rng(self.seed)

    def simulate(self) -> np.ndarray:
        return self._rng().binomial(self.quantity, self.probability, self.iterations)

    def simulate_day(self, productions_per_day: int = 1) -> np.ndarray:
        return self._rng().binomial(
            self.quantity * productions_per_day, self.probability, self.iterations
        )

    def simulate_month(self, productions_per_day: int = 1, days: int = 30) -> np.ndarray:
        return self._rng().binomial(
            self.quantity * productions_per_day * days, self.probability, self.iterations
        )

    def simulate_year(self, productions_per_day: int = 1, days: int = 365) -> np.ndarray:
        return self._rng().binomial(
            self.quantity * productions_per_day * days, self.probability, self.iterations
        )
