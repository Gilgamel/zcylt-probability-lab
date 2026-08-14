"""Reusable statistical calculations for the unified observation pipeline."""

from dataclasses import dataclass
from math import ceil

import numpy as np
from scipy.stats import binomtest, chisquare, chi2_contingency, norm
from statsmodels.stats.proportion import proportion_confint, proportions_ztest


def calculate_drop_rate(successes: int, total: int) -> float:
    """Return an observed probability, or zero when no trials exist."""
    return successes / total if total > 0 else 0.0


def confidence_interval(
    successes: int,
    total: int,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Return a Wilson score confidence interval for a binomial probability."""
    if total <= 0:
        return 0.0, 0.0
    low, high = proportion_confint(successes, total, alpha=alpha, method="wilson")
    return float(low), float(high)


def sample_size(total: int) -> int:
    """Return a non-negative number of trials."""
    return max(0, int(total))


def binomial_test(successes: int, total: int, expected_probability: float) -> float:
    """Return a two-sided exact binomial hypothesis-test p-value."""
    if total <= 0:
        raise ValueError("样本量必须大于 0")
    if not 0 <= expected_probability <= 1:
        raise ValueError("期望概率必须在 0 和 1 之间")
    return float(binomtest(successes, total, expected_probability).pvalue)


def chi_square_test(table: list[list[int]] | np.ndarray) -> tuple[float, float]:
    """Run Pearson's chi-square independence test on a contingency table."""
    statistic, p_value, _, _ = chi2_contingency(table)
    return float(statistic), float(p_value)


def chi_square_goodness_of_fit(
    observed: list[int] | np.ndarray,
    expected_probabilities: list[float] | np.ndarray,
) -> tuple[float, float]:
    """Test observed category counts against an explicit probability vector."""
    observed_array = np.asarray(observed, dtype=float)
    probabilities = np.asarray(expected_probabilities, dtype=float)
    if observed_array.ndim != 1 or probabilities.shape != observed_array.shape:
        raise ValueError("观测数量和期望概率必须是一维且长度相同")
    if observed_array.sum() <= 0 or np.any(observed_array < 0):
        raise ValueError("观测数量必须非负且总数大于 0")
    if np.any(probabilities < 0) or not np.isclose(probabilities.sum(), 1.0):
        raise ValueError("期望概率合计必须为 1")
    expected = probabilities * observed_array.sum()
    if np.any(expected < 5):
        raise ValueError("期望频数小于 5，不满足卡方检验条件")
    statistic, p_value = chisquare(observed_array, expected)
    return float(statistic), float(p_value)


def proportion_z_test(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> tuple[float, float]:
    """Run a two-sample proportion z-test."""
    if total_a <= 0 or total_b <= 0:
        raise ValueError("两组样本量必须大于 0")
    statistic, p_value = proportions_ztest(
        [successes_a, successes_b], [total_a, total_b]
    )
    return float(statistic), float(p_value)


def required_sample_size(
    probability: float,
    margin_of_error: float,
    alpha: float = 0.05,
) -> int:
    """Estimate binomial trials required for an absolute margin of error."""
    if not 0 < margin_of_error < 1:
        raise ValueError("目标误差必须在 0 和 1 之间")
    if not 0 <= probability <= 1:
        raise ValueError("概率必须在 0 和 1 之间")
    working_probability = probability if 0 < probability < 1 else 0.5
    z_score = float(norm.ppf(1 - alpha / 2))
    return ceil(z_score**2 * working_probability * (1 - working_probability) / margin_of_error**2)


@dataclass(frozen=True)
class SufficiencyThresholds:
    """Configurable absolute margin-of-error thresholds."""

    grade_a: float = 0.005
    grade_b: float = 0.010
    grade_c: float = 0.020

    def __post_init__(self) -> None:
        if not 0 < self.grade_a <= self.grade_b <= self.grade_c < 1:
            raise ValueError("样本评级阈值必须递增且位于 0 和 1 之间")


@dataclass(frozen=True)
class Sufficiency:
    """Precision and collection guidance for one probability target."""

    sample_count: int
    rate: float
    ci_low: float
    ci_high: float
    absolute_ci_width: float
    margin_of_error: float
    required_samples: int
    additional_samples: int
    grade: str
    label: str


def sample_sufficiency(
    successes: int,
    total: int,
    thresholds: SufficiencyThresholds | None = None,
    target_margin: float = 0.005,
    planning_probability: float | None = None,
) -> Sufficiency:
    """Summarize precision, rating, and additional data required."""
    thresholds = thresholds or SufficiencyThresholds()
    rate = calculate_drop_rate(successes, total)
    low, high = confidence_interval(successes, total)
    width = high - low
    margin = width / 2
    planning_p = planning_probability if planning_probability is not None else rate
    required = required_sample_size(planning_p, target_margin)
    additional = max(0, required - total)
    if total == 0 or margin > thresholds.grade_c:
        grade, label = "D", "样本不足"
    elif margin <= thresholds.grade_a:
        grade, label = "A", "非常可靠"
    elif margin <= thresholds.grade_b:
        grade, label = "B", "可用"
    else:
        grade, label = "C", "初步结果"
    return Sufficiency(
        total, rate, low, high, width, margin, required, additional, grade, label
    )


def session_probability_at_least_one(probability: float, searches: int) -> float:
    """Calculate P(X >= 1) for an independent n-search session."""
    if not 0 <= probability <= 1 or searches <= 0:
        raise ValueError("概率或搜索次数无效")
    return 1 - (1 - probability) ** searches
