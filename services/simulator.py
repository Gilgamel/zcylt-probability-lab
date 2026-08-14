"""Reproducible vectorized Monte Carlo models."""

from dataclasses import dataclass

import numpy as np


@dataclass
class ProductionSimulator:
    """Independent binomial simulator for red/orange outcomes."""

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
        """Simulate one batch per iteration."""
        return self._rng().binomial(self.quantity, self.probability, self.iterations)

    def simulate_day(self, productions_per_day: int = 1) -> np.ndarray:
        """Simulate total successes per day."""
        return self._rng().binomial(
            self.quantity * productions_per_day, self.probability, self.iterations
        )

    def simulate_month(self, productions_per_day: int = 1, days: int = 30) -> np.ndarray:
        """Simulate total successes per month."""
        return self._rng().binomial(
            self.quantity * productions_per_day * days,
            self.probability,
            self.iterations,
        )

    def simulate_year(self, productions_per_day: int = 1, days: int = 365) -> np.ndarray:
        """Simulate total successes per year."""
        return self._rng().binomial(
            self.quantity * productions_per_day * days,
            self.probability,
            self.iterations,
        )


@dataclass
class CategoricalSimulator:
    """Multinomial simulator for horse or bird quality distributions."""

    probabilities: dict[str, float]
    searches_per_session: int
    iterations: int
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.searches_per_session <= 0 or self.iterations <= 0:
            raise ValueError("搜索次数和迭代次数必须大于 0")
        values = np.asarray(list(self.probabilities.values()), dtype=float)
        if np.any(values < 0) or not np.isclose(values.sum(), 1.0):
            raise ValueError("模拟概率合计必须为 1；不会自动归一化")

    @property
    def labels(self) -> tuple[str, ...]:
        """Return result labels in probability insertion order."""
        return tuple(self.probabilities)

    def simulate(self) -> np.ndarray:
        """Return an iterations × categories matrix of session counts."""
        return np.random.default_rng(self.seed).multinomial(
            self.searches_per_session,
            list(self.probabilities.values()),
            self.iterations,
        )

    def outcome_counts(self, label: str) -> np.ndarray:
        """Return the simulated count for one named category per session."""
        if label not in self.probabilities:
            raise ValueError(f"模拟中不存在结果：{label}")
        return self.simulate()[:, self.labels.index(label)]


def literal_horse_probabilities(displayed: dict[str, float]) -> dict[str, float]:
    """Add an explicit OTHER remainder without altering displayed values."""
    total = sum(displayed.values())
    if total > 1 + 1e-12:
        raise ValueError("显示概率合计超过 100%")
    return {**displayed, "OTHER": max(0.0, 1 - total)}


def normalized_probabilities(displayed: dict[str, float]) -> dict[str, float]:
    """Normalize probabilities solely for an explicitly labeled simulation mode."""
    total = sum(displayed.values())
    if total <= 0:
        raise ValueError("无法归一化空概率")
    return {quality: probability / total for quality, probability in displayed.items()}


def simulation_interval(values: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    """Return an empirical central simulation interval."""
    if values.size == 0:
        raise ValueError("模拟结果为空")
    low, high = np.quantile(values, [alpha / 2, 1 - alpha / 2])
    return float(low), float(high)


def simulate_mixed_sessions(
    probability: float,
    observed_session_sizes: np.ndarray,
    iterations: int,
    seed: int | None = None,
) -> np.ndarray:
    """Simulate sessions using the empirical distribution of session sizes."""
    sizes = np.asarray(observed_session_sizes, dtype=int)
    if sizes.size == 0 or np.any(sizes <= 0):
        raise ValueError("实际会话规模必须为正且不能为空")
    if not 0 <= probability <= 1 or iterations <= 0:
        raise ValueError("概率或迭代次数无效")
    rng = np.random.default_rng(seed)
    sampled_sizes = rng.choice(sizes, size=iterations, replace=True)
    return rng.binomial(sampled_sizes, probability)
