"""Statistical calculations for observed drop data."""

from dataclasses import dataclass

import numpy as np
from scipy.stats import binomtest, chi2_contingency
from statsmodels.stats.proportion import proportion_confint, proportions_ztest


def calculate_drop_rate(red: int, total: int) -> float:
    """Return the observed proportion, or zero without observations."""
    return red / total if total > 0 else 0.0


def confidence_interval(red: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if total <= 0:
        return 0.0, 0.0
    low, high = proportion_confint(red, total, alpha=alpha, method="wilson")
    return float(low), float(high)


def sample_size(total: int) -> int:
    """Return the number of individual production trials."""
    return max(0, int(total))


def binomial_test(red: int, total: int, expected_probability: float) -> float:
    """Two-sided exact binomial hypothesis test p-value."""
    if total <= 0:
        raise ValueError("样本量必须大于 0")
    return float(binomtest(red, total, expected_probability).pvalue)


def chi_square_test(table: list[list[int]] | np.ndarray) -> tuple[float, float]:
    """Pearson chi-square test for a contingency table."""
    statistic, p_value, _, _ = chi2_contingency(table)
    return float(statistic), float(p_value)


def proportion_z_test(
    red_a: int, total_a: int, red_b: int, total_b: int
) -> tuple[float, float]:
    """Two-sample proportion z-test."""
    if total_a <= 0 or total_b <= 0:
        raise ValueError("两组样本量必须大于 0")
    statistic, p_value = proportions_ztest([red_a, red_b], [total_a, total_b])
    return float(statistic), float(p_value)


@dataclass(frozen=True)
class Sufficiency:
    """Sample-quality summary."""

    sample_count: int
    rate: float
    ci_low: float
    ci_high: float
    margin_of_error: float
    grade: str
    label: str


def sample_sufficiency(red: int, total: int) -> Sufficiency:
    """Grade precision using the Wilson interval margin of error."""
    rate = calculate_drop_rate(red, total)
    low, high = confidence_interval(red, total)
    margin = (high - low) / 2
    if total >= 5000 and margin <= 0.01:
        grade, label = "A", "非常可靠"
    elif total >= 2000 and margin <= 0.02:
        grade, label = "B", "可靠"
    elif total >= 500:
        grade, label = "C", "需要更多数据"
    else:
        grade, label = "D", "样本不足"
    return Sufficiency(total, rate, low, high, margin, grade, label)
