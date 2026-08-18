"""Statistically explicit Monte Carlo models for ProbabilityLab Phase 4.

Simulation intervals describe outcomes generated under a selected model.  They
are not confidence intervals and do not replace Phase 3 hypothesis tests.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt
import secrets
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import binom

from services.simulator import CategoricalSimulator, ProductionSimulator


RESULT_VERSION = 1
MATERIAL_USER_MODEL = "material_user_probability"
MATERIAL_EMPIRICAL_MODEL = "material_empirical_probability"
HORSE_LITERAL_MODEL = "horse_literal_multinomial"
BIRD_QUALITY_MODEL = "bird_quality_multinomial"
BIRD_EQUAL_SPECIES_MODEL = "equal_25_percent_hypothesis"
DEFAULT_SIMULATIONS = 100_000
SIMULATION_OPTIONS = (10_000, 50_000, 100_000, 250_000, 500_000)
MAX_SIMULATIONS = 500_000
MAX_TRIALS = 10_000_000
MAX_SEED = 2_147_483_647


@dataclass(frozen=True)
class OutcomeSummary:
    """One simulated count distribution and optional actual comparison."""

    expected: float
    theoretical_std: float
    mean: float
    median: float
    std: float
    minimum: int
    maximum: int
    quantiles: dict[str, float]
    simulation_interval: tuple[float, float]
    simulation_interval_99: tuple[float, float]
    actual_count: int | None
    actual_percentile: float | None
    empirical_tail_probability: float | None
    monte_carlo_tail_se: float | None
    difference_from_expected: float | None
    standardized_difference: float | None
    classification: str

    def storage_dict(self) -> dict[str, object]:
        return {
            "expected": self.expected,
            "theoretical_std": self.theoretical_std,
            "mean": self.mean,
            "median": self.median,
            "std": self.std,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "quantiles": self.quantiles,
            "simulation_interval": list(self.simulation_interval),
            "simulation_interval_99": list(self.simulation_interval_99),
            "actual_count": self.actual_count,
            "actual_percentile": self.actual_percentile,
            "empirical_tail_probability": self.empirical_tail_probability,
            "monte_carlo_tail_se": self.monte_carlo_tail_se,
            "difference_from_expected": self.difference_from_expected,
            "standardized_difference": self.standardized_difference,
            "classification": self.classification,
        }


@dataclass(frozen=True)
class BinaryMonteCarloResult:
    target_probability: float
    trial_count: int
    simulation_count: int
    random_seed: int
    samples: np.ndarray
    outcome: OutcomeSummary
    actual_trials: int | None = None

    @property
    def actual_rate(self) -> float | None:
        if self.outcome.actual_count is None or not self.actual_trials:
            return None
        return self.outcome.actual_count / self.actual_trials

    @property
    def actual_comparable(self) -> bool:
        return (
            self.outcome.actual_count is not None
            and self.actual_trials == self.trial_count
        )

    def storage_dict(self) -> dict[str, object]:
        """Return versioned JSON-safe summary; raw simulations are excluded."""
        return {
            "result_version": RESULT_VERSION,
            "model_type": "binomial",
            "target_probability": self.target_probability,
            "trial_count": self.trial_count,
            "simulation_count": self.simulation_count,
            "seed": self.random_seed,
            **self.outcome.storage_dict(),
            "actual_trials": self.actual_trials,
            "actual_rate": self.actual_rate,
            "actual_comparable": self.actual_comparable,
        }


@dataclass(frozen=True)
class MultinomialMonteCarloResult:
    categories: tuple[str, ...]
    probabilities: tuple[float, ...]
    trial_count: int
    simulation_count: int
    random_seed: int
    samples: np.ndarray
    per_category: dict[str, OutcomeSummary]
    actual_counts: dict[str, int] | None = None
    actual_trials: int | None = None

    @property
    def actual_comparable(self) -> bool:
        return self.actual_counts is not None and self.actual_trials == self.trial_count

    @property
    def classification(self) -> str:
        rankings = {
            "No actual observation comparison": 0,
            "Consistent with the theoretical model": 1,
            "Unusual under the theoretical model": 2,
            "Very unusual under the theoretical model": 3,
        }
        return max(
            (summary.classification for summary in self.per_category.values()),
            key=lambda label: rankings[label],
        )

    def storage_dict(self) -> dict[str, object]:
        """Return versioned JSON-safe summary; raw simulations are excluded."""
        return {
            "result_version": RESULT_VERSION,
            "model_type": "multinomial",
            "categories": list(self.categories),
            "probabilities": list(self.probabilities),
            "trial_count": self.trial_count,
            "simulation_count": self.simulation_count,
            "seed": self.random_seed,
            "per_category_summary": {
                category: summary.storage_dict()
                for category, summary in self.per_category.items()
            },
            "actual_counts": self.actual_counts,
            "actual_percentiles": {
                category: summary.actual_percentile
                for category, summary in self.per_category.items()
            },
            "simulation_intervals": {
                category: list(summary.simulation_interval)
                for category, summary in self.per_category.items()
            },
            "actual_trials": self.actual_trials,
            "actual_comparable": self.actual_comparable,
            "classification": self.classification,
        }


def _validate_common(trial_count: int, simulation_count: int) -> None:
    if type(trial_count) is not int or not 1 <= trial_count <= MAX_TRIALS:
        raise ValueError(f"trial_count 必须是 1 到 {MAX_TRIALS:,} 的整数")
    if type(simulation_count) is not int or not 1 <= simulation_count <= MAX_SIMULATIONS:
        raise ValueError(f"simulation_count 必须是 1 到 {MAX_SIMULATIONS:,} 的整数")


def _resolve_seed(seed: int | None) -> int:
    if seed is None:
        return secrets.randbelow(MAX_SEED + 1)
    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"随机种子必须是 0 到 {MAX_SEED:,} 的整数")
    return seed


def _classification(actual: int | None, interval95: tuple[float, float], interval99: tuple[float, float]) -> str:
    if actual is None:
        return "No actual observation comparison"
    if actual < interval99[0] or actual > interval99[1]:
        return "Very unusual under the theoretical model"
    if actual < interval95[0] or actual > interval95[1]:
        return "Unusual under the theoretical model"
    return "Consistent with the theoretical model"


def _summarize_outcomes(
    values: np.ndarray,
    expected: float,
    theoretical_std: float,
    actual_count: int | None,
) -> OutcomeSummary:
    quantile_values = np.quantile(
        values,
        [0.005, 0.01, 0.025, 0.05, 0.25, 0.50, 0.75, 0.95, 0.975, 0.99, 0.995],
    )
    quantiles = {
        "p01": float(quantile_values[1]),
        "p05": float(quantile_values[3]),
        "p25": float(quantile_values[4]),
        "p50": float(quantile_values[5]),
        "p75": float(quantile_values[6]),
        "p95": float(quantile_values[7]),
        "p99": float(quantile_values[9]),
    }
    interval95 = float(quantile_values[2]), float(quantile_values[8])
    interval99 = float(quantile_values[0]), float(quantile_values[10])
    percentile: float | None = None
    tail_probability: float | None = None
    tail_se: float | None = None
    difference: float | None = None
    standardized: float | None = None
    if actual_count is not None:
        percentile = float(np.mean(values <= actual_count))
        # Discrete two-sided empirical tail: count simulated outcomes at least
        # as far from the theoretical expected count as the actual result.
        # The plus-one correction prevents a reported probability of exactly 0.
        distance = abs(actual_count - expected)
        extreme = int(np.count_nonzero(np.abs(values - expected) >= distance))
        tail_probability = (extreme + 1) / (values.size + 1)
        tail_se = sqrt(tail_probability * (1 - tail_probability) / values.size)
        difference = actual_count - expected
        standardized = difference / theoretical_std if theoretical_std > 0 else None
    return OutcomeSummary(
        expected=float(expected),
        theoretical_std=float(theoretical_std),
        mean=float(np.mean(values)),
        median=float(np.median(values)),
        std=float(np.std(values)),
        minimum=int(np.min(values)),
        maximum=int(np.max(values)),
        quantiles=quantiles,
        simulation_interval=interval95,
        simulation_interval_99=interval99,
        actual_count=actual_count,
        actual_percentile=percentile,
        empirical_tail_probability=tail_probability,
        monte_carlo_tail_se=tail_se,
        difference_from_expected=difference,
        standardized_difference=standardized,
        classification=_classification(actual_count, interval95, interval99),
    )


def simulate_binary(
    target_probability: float,
    trial_count: int,
    simulation_count: int = DEFAULT_SIMULATIONS,
    seed: int | None = None,
    *,
    actual_successes: int | None = None,
    actual_trials: int | None = None,
) -> BinaryMonteCarloResult:
    """Simulate independent Binomial datasets and compare an optional actual count."""
    _validate_common(trial_count, simulation_count)
    if not 0 <= target_probability <= 1:
        raise ValueError("目标概率必须在 0 和 1 之间")
    if (actual_successes is None) != (actual_trials is None):
        raise ValueError("实际成功数和实际试验数必须同时提供")
    if actual_trials is not None and (
        actual_trials <= 0 or actual_successes is None
        or not 0 <= actual_successes <= actual_trials
    ):
        raise ValueError("实际观测计数无效")
    used_seed = _resolve_seed(seed)
    values = ProductionSimulator(
        target_probability, trial_count, simulation_count, used_seed
    ).simulate()
    comparable_actual = actual_successes if actual_trials == trial_count else None
    expected = trial_count * target_probability
    theoretical_std = sqrt(trial_count * target_probability * (1 - target_probability))
    outcome = _summarize_outcomes(values, expected, theoretical_std, comparable_actual)
    if actual_successes is not None and comparable_actual is None:
        outcome = replace(
            outcome,
            actual_count=actual_successes,
            classification="No actual observation comparison",
        )
    return BinaryMonteCarloResult(
        target_probability, trial_count, simulation_count, used_seed,
        values, outcome, actual_trials,
    )


def simulate_multinomial(
    probabilities: Mapping[str, float],
    trial_count: int,
    simulation_count: int = DEFAULT_SIMULATIONS,
    seed: int | None = None,
    *,
    actual_counts: Mapping[str, int] | None = None,
    actual_trials: int | None = None,
) -> MultinomialMonteCarloResult:
    """Simulate independent Multinomial datasets and compare category counts."""
    _validate_common(trial_count, simulation_count)
    if len(probabilities) < 2:
        raise ValueError("多项式模型至少需要两个类别")
    categories = tuple(probabilities)
    probability_values = np.asarray(tuple(probabilities.values()), dtype=float)
    if np.any(~np.isfinite(probability_values)) or np.any(probability_values < 0):
        raise ValueError("类别概率必须是非负有限数")
    if not np.isclose(probability_values.sum(), 1.0, atol=1e-12):
        raise ValueError("多项式概率合计必须为 1；不会自动归一化")
    normalized_actual: dict[str, int] | None = None
    if actual_counts is not None:
        if set(actual_counts) != set(categories):
            raise ValueError("实际类别必须与模拟类别完全一致")
        normalized_actual = {key: int(actual_counts[key]) for key in categories}
        if any(value < 0 for value in normalized_actual.values()):
            raise ValueError("实际类别计数不能为负")
        if actual_trials is None or sum(normalized_actual.values()) != actual_trials:
            raise ValueError("实际类别计数合计必须等于实际试验数")
    elif actual_trials is not None:
        raise ValueError("提供实际试验数时必须提供实际类别计数")
    used_seed = _resolve_seed(seed)
    matrix = CategoricalSimulator(
        dict(zip(categories, probability_values, strict=True)),
        trial_count,
        simulation_count,
        used_seed,
    ).simulate()
    comparable = normalized_actual if actual_trials == trial_count else None
    summaries: dict[str, OutcomeSummary] = {}
    for index, category in enumerate(categories):
        probability = float(probability_values[index])
        actual = comparable[category] if comparable is not None else None
        summary = _summarize_outcomes(
            matrix[:, index],
            trial_count * probability,
            sqrt(trial_count * probability * (1 - probability)),
            actual,
        )
        if normalized_actual is not None and comparable is None:
            summary = replace(
                summary,
                actual_count=normalized_actual[category],
                classification="No actual observation comparison",
            )
        summaries[category] = summary
    return MultinomialMonteCarloResult(
        categories,
        tuple(float(value) for value in probability_values),
        trial_count,
        simulation_count,
        used_seed,
        matrix,
        summaries,
        normalized_actual,
        actual_trials,
    )


def binary_summary_frame(result: BinaryMonteCarloResult) -> pd.DataFrame:
    """Return one presentation-ready row for a binary simulation."""
    summary = result.outcome
    return pd.DataFrame([{
        "target_probability": result.target_probability,
        "actual_count": summary.actual_count,
        "actual_rate": result.actual_rate,
        "expected_count": summary.expected,
        "simulation_mean": summary.mean,
        "simulation_median": summary.median,
        "simulation_std": summary.std,
        "theoretical_std": summary.theoretical_std,
        "minimum": summary.minimum,
        "maximum": summary.maximum,
        **summary.quantiles,
        "interval_95_low": summary.simulation_interval[0],
        "interval_95_high": summary.simulation_interval[1],
        "interval_99_low": summary.simulation_interval_99[0],
        "interval_99_high": summary.simulation_interval_99[1],
        "actual_percentile": summary.actual_percentile,
        "empirical_tail_probability": summary.empirical_tail_probability,
        "monte_carlo_tail_se": summary.monte_carlo_tail_se,
        "difference_from_expected": summary.difference_from_expected,
        "standardized_difference": summary.standardized_difference,
        "classification": summary.classification,
    }])


def multinomial_summary_frame(result: MultinomialMonteCarloResult) -> pd.DataFrame:
    """Return one presentation-ready row per multinomial category."""
    rows = []
    for category, probability in zip(result.categories, result.probabilities, strict=True):
        summary = result.per_category[category]
        rows.append({
            "category": category,
            "target_probability": probability,
            "actual_count": summary.actual_count,
            "expected_count": summary.expected,
            "simulation_mean": summary.mean,
            "simulation_median": summary.median,
            "simulation_std": summary.std,
            "theoretical_std": summary.theoretical_std,
            "minimum": summary.minimum,
            "maximum": summary.maximum,
            **summary.quantiles,
            "interval_95_low": summary.simulation_interval[0],
            "interval_95_high": summary.simulation_interval[1],
            "interval_99_low": summary.simulation_interval_99[0],
            "interval_99_high": summary.simulation_interval_99[1],
            "actual_percentile": summary.actual_percentile,
            "empirical_tail_probability": summary.empirical_tail_probability,
            "monte_carlo_tail_se": summary.monte_carlo_tail_se,
            "difference_from_expected": summary.difference_from_expected,
            "standardized_difference": summary.standardized_difference,
            "classification": summary.classification,
        })
    return pd.DataFrame(rows)


def session_probability_frame(
    result: BinaryMonteCarloResult,
    actual_session_successes: Sequence[int] | np.ndarray | None = None,
) -> pd.DataFrame:
    """Compare simulated session counts with exact Binomial probabilities."""
    actual = (
        np.asarray(actual_session_successes, dtype=int)
        if actual_session_successes is not None else np.asarray([], dtype=int)
    )
    if actual.size and (np.any(actual < 0) or np.any(actual > result.trial_count)):
        raise ValueError("实际会话成功数超出有效范围")
    rows = []
    for successes in range(result.trial_count + 1):
        rows.append({
            "successes": successes,
            "simulated_probability": float(np.mean(result.samples == successes)),
            "exact_probability": float(
                binom.pmf(successes, result.trial_count, result.target_probability)
            ),
            "actual_sessions": int(np.count_nonzero(actual == successes)),
            "actual_probability": (
                float(np.mean(actual == successes)) if actual.size else None
            ),
        })
    return pd.DataFrame(rows)
