"""Pure statistical calculations for ProbabilityLab.

All public Phase 3 functions are independent of Streamlit and the database.  A
missing sample is represented by ``None`` in structured results so the UI never
misrepresents "not measured" as a zero-percent observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Sequence

import numpy as np
from scipy.stats import binom, binomtest, chisquare, chi2_contingency, fisher_exact, norm
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint, proportions_ztest


@dataclass(frozen=True)
class ProportionResult:
    successes: int
    trials: int
    observed_rate: float | None
    ci_low: float | None
    ci_high: float | None
    confidence_level: float = 0.95

    @property
    def ci_width(self) -> float | None:
        if self.ci_low is None or self.ci_high is None:
            return None
        return self.ci_high - self.ci_low


@dataclass(frozen=True)
class HypothesisTestResult:
    test_name: str
    statistic: float | None
    p_value: float
    alpha: float = 0.05
    note: str = ""

    @property
    def significant(self) -> bool:
        return self.p_value < self.alpha


@dataclass(frozen=True)
class ProportionComparisonResult:
    label_a: str
    label_b: str
    rate_a: float
    rate_b: float
    absolute_difference: float
    percentage_point_difference: float
    test: HypothesisTestResult
    adjusted_p_value: float | None = None


@dataclass(frozen=True)
class ChiSquareResult:
    statistic: float
    p_value: float
    degrees_of_freedom: int
    observed: tuple[int, ...]
    expected: tuple[float, ...]
    residuals: tuple[float, ...]


@dataclass(frozen=True)
class SampleSizeResult:
    planning_probability: float
    confidence_level: float
    target_margin_of_error: float
    current_samples: int
    required_samples: int
    remaining_samples: int


@dataclass(frozen=True)
class SessionProbabilityResult:
    probability: float
    searches: int
    zero: float
    exactly_one: float
    at_least_one: float
    at_least_two: float


@dataclass(frozen=True)
class ProbabilityDifference:
    observed: float
    target: float
    absolute_difference: float
    percentage_point_difference: float


def _validate_binomial(successes: int, trials: int, *, allow_empty: bool = False) -> None:
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("成功次数必须位于 0 到总次数之间")
    if trials == 0 and not allow_empty:
        raise ValueError("样本量必须大于 0")


def calculate_observed_rate(successes: int, trials: int) -> float | None:
    """Return the raw observed proportion; ``None`` means no measurement."""
    _validate_binomial(successes, trials, allow_empty=True)
    return successes / trials if trials else None


def calculate_wilson_ci(
    successes: int, trials: int, confidence_level: float = 0.95
) -> tuple[float | None, float | None]:
    """Return a Wilson score interval, the primary ProbabilityLab interval."""
    _validate_binomial(successes, trials, allow_empty=True)
    if not 0 < confidence_level < 1:
        raise ValueError("置信水平必须位于 0 和 1 之间")
    if trials == 0:
        return None, None
    low, high = proportion_confint(
        successes, trials, alpha=1 - confidence_level, method="wilson"
    )
    observed = successes / trials
    # Clamp harmless floating-point drift so boundary samples still satisfy
    # lower <= p_hat <= upper exactly (statsmodels can return 0.9999999999999999).
    return max(0.0, min(observed, float(low))), min(1.0, max(observed, float(high)))


def calculate_proportion(
    successes: int, trials: int, confidence_level: float = 0.95
) -> ProportionResult:
    rate = calculate_observed_rate(successes, trials)
    low, high = calculate_wilson_ci(successes, trials, confidence_level)
    return ProportionResult(successes, trials, rate, low, high, confidence_level)


def calculate_binomial_test(
    successes: int,
    trials: int,
    expected_probability: float,
    alpha: float = 0.05,
) -> HypothesisTestResult:
    """Run a two-sided exact binomial test against an explicit target."""
    _validate_binomial(successes, trials)
    if not 0 <= expected_probability <= 1:
        raise ValueError("期望概率必须在 0 和 1 之间")
    result = binomtest(successes, trials, expected_probability)
    return HypothesisTestResult(
        "Exact binomial test", None, float(result.pvalue), alpha,
        f"H0: p = {expected_probability:.6g}",
    )


def calculate_probability_difference(observed: float, target: float) -> ProbabilityDifference:
    """Return signed probability-unit and percentage-point differences."""
    if not 0 <= observed <= 1 or not 0 <= target <= 1:
        raise ValueError("概率必须在 0 和 1 之间")
    difference = observed - target
    return ProbabilityDifference(observed, target, difference, difference * 100)


def calculate_two_proportion_test(
    successes_a: int,
    trials_a: int,
    successes_b: int,
    trials_b: int,
    *,
    label_a: str = "A",
    label_b: str = "B",
    alpha: float = 0.05,
) -> ProportionComparisonResult:
    """Compare two independent rates, using Fisher's exact test when sparse."""
    _validate_binomial(successes_a, trials_a)
    _validate_binomial(successes_b, trials_b)
    table = np.asarray(
        [[successes_a, trials_a - successes_a],
         [successes_b, trials_b - successes_b]], dtype=int
    )
    pooled = (successes_a + successes_b) / (trials_a + trials_b)
    expected = np.asarray([
        trials_a * pooled,
        trials_a * (1 - pooled),
        trials_b * pooled,
        trials_b * (1 - pooled),
    ])
    if np.any(expected < 5):
        odds_ratio, p_value = fisher_exact(table, alternative="two-sided")
        statistic = None if np.isnan(odds_ratio) else float(odds_ratio)
        test_name = "Fisher exact test"
    else:
        statistic, p_value = proportions_ztest(
            [successes_a, successes_b], [trials_a, trials_b]
        )
        statistic, p_value = float(statistic), float(p_value)
        test_name = "Two-proportion z-test"
    rate_a = successes_a / trials_a
    rate_b = successes_b / trials_b
    difference = rate_a - rate_b
    return ProportionComparisonResult(
        label_a, label_b, rate_a, rate_b, difference, difference * 100,
        HypothesisTestResult(test_name, statistic, float(p_value), alpha),
    )


def apply_holm_correction(
    comparisons: Sequence[ProportionComparisonResult], alpha: float = 0.05
) -> list[ProportionComparisonResult]:
    """Return comparisons with family-wise Holm-adjusted p-values."""
    if not comparisons:
        return []
    adjusted = multipletests(
        [item.test.p_value for item in comparisons], alpha=alpha, method="holm"
    )[1]
    return [
        ProportionComparisonResult(
            item.label_a, item.label_b, item.rate_a, item.rate_b,
            item.absolute_difference, item.percentage_point_difference,
            HypothesisTestResult(
                item.test.test_name, item.test.statistic, item.test.p_value,
                alpha, item.test.note,
            ),
            float(adjusted[index]),
        )
        for index, item in enumerate(comparisons)
    ]


def interpret_p_value(
    p_value: float, null_description: str, alpha: float = 0.05
) -> str:
    """Return cautious hypothesis-test language without accepting the null."""
    if not 0 <= p_value <= 1 or not 0 < alpha < 1:
        raise ValueError("p 值或显著性水平无效")
    if p_value < alpha:
        return f"数据提供反对“{null_description}”的统计证据（α={alpha:.2f}）。"
    return (
        f"证据不足以拒绝“{null_description}”（α={alpha:.2f}）；"
        "这不等于证明该假设正确。"
    )


def calculate_chi_square_gof(
    observed: Sequence[int], expected_probabilities: Sequence[float], alpha: float = 0.05
) -> ChiSquareResult:
    """Pearson goodness-of-fit test for a fully specified category vector."""
    observed_array = np.asarray(observed, dtype=float)
    probabilities = np.asarray(expected_probabilities, dtype=float)
    if observed_array.ndim != 1 or probabilities.shape != observed_array.shape:
        raise ValueError("观测数量和期望概率必须是一维且长度相同")
    if observed_array.size < 2 or observed_array.sum() <= 0 or np.any(observed_array < 0):
        raise ValueError("观测数量必须非负、总数大于 0 且至少包含两类")
    if np.any(probabilities <= 0) or not np.isclose(probabilities.sum(), 1.0):
        raise ValueError("期望概率必须为正且合计为 1")
    expected = probabilities * observed_array.sum()
    if np.any(expected < 5):
        raise ValueError("期望频数小于 5，不满足卡方近似条件")
    statistic, p_value = chisquare(observed_array, expected)
    residuals = (observed_array - expected) / np.sqrt(expected)
    return ChiSquareResult(
        float(statistic), float(p_value), int(observed_array.size - 1),
        tuple(int(value) for value in observed_array),
        tuple(float(value) for value in expected),
        tuple(float(value) for value in residuals),
    )


def calculate_sample_size(
    probability: float,
    margin_of_error: float,
    confidence_level: float = 0.95,
    current_samples: int = 0,
) -> SampleSizeResult:
    """Approximate binomial sample planning using a normal-margin formula."""
    if not 0 < margin_of_error < 1:
        raise ValueError("目标误差必须在 0 和 1 之间")
    if not 0 <= probability <= 1:
        raise ValueError("概率必须在 0 和 1 之间")
    if not 0 < confidence_level < 1 or current_samples < 0:
        raise ValueError("置信水平或当前样本量无效")
    planning_probability = probability if 0 < probability < 1 else 0.5
    z_score = float(norm.ppf(0.5 + confidence_level / 2))
    required = ceil(
        z_score**2 * planning_probability * (1 - planning_probability)
        / margin_of_error**2
    )
    return SampleSizeResult(
        planning_probability, confidence_level, margin_of_error, current_samples,
        required, max(0, required - current_samples),
    )


def calculate_margin_of_error(result: ProportionResult) -> float | None:
    """Return half the Wilson interval width."""
    return None if result.ci_width is None else result.ci_width / 2


def calculate_session_probability(probability: float, searches: int = 8) -> SessionProbabilityResult:
    """Exact binomial probabilities for zero, >=1 and >=2 successes."""
    if not 0 <= probability <= 1 or searches <= 0:
        raise ValueError("概率或搜索次数无效")
    zero = float(binom.pmf(0, searches, probability))
    one = float(binom.pmf(1, searches, probability))
    return SessionProbabilityResult(probability, searches, zero, one, 1 - zero, 1 - zero - one)


def classify_sample_quality(result: ProportionResult) -> str:
    """Classify precision by actual n and Wilson width.

    Width thresholds: >20 pp Very Low, >10 pp Low, >5 pp Moderate,
    otherwise Good.  Fewer than 30 trials cannot exceed Very Low and fewer
    than 100 cannot exceed Low, preventing deceptively narrow extreme-rate
    intervals from receiving a strong label.
    """
    if result.trials == 0 or result.ci_width is None:
        return "No Data"
    if result.trials < 30 or result.ci_width > 0.20:
        return "Very Low"
    if result.trials < 100 or result.ci_width > 0.10:
        return "Low"
    if result.ci_width > 0.05:
        return "Moderate"
    return "Good"


# Backward-compatible Phase 1/2 API -----------------------------------------

def calculate_drop_rate(successes: int, total: int) -> float:
    return calculate_observed_rate(successes, total) or 0.0


def confidence_interval(successes: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    low, high = calculate_wilson_ci(successes, total, 1 - alpha)
    return (low or 0.0), (high or 0.0)


def sample_size(total: int) -> int:
    return max(0, int(total))


def binomial_test(successes: int, total: int, expected_probability: float) -> float:
    return calculate_binomial_test(successes, total, expected_probability).p_value


def chi_square_test(table: list[list[int]] | np.ndarray) -> tuple[float, float]:
    statistic, p_value, _, _ = chi2_contingency(table)
    return float(statistic), float(p_value)


def chi_square_goodness_of_fit(
    observed: list[int] | np.ndarray, expected_probabilities: list[float] | np.ndarray
) -> tuple[float, float]:
    result = calculate_chi_square_gof(observed, expected_probabilities)
    return result.statistic, result.p_value


def proportion_z_test(
    successes_a: int, total_a: int, successes_b: int, total_b: int
) -> tuple[float, float]:
    _validate_binomial(successes_a, total_a)
    _validate_binomial(successes_b, total_b)
    statistic, p_value = proportions_ztest(
        [successes_a, successes_b], [total_a, total_b]
    )
    return float(statistic), float(p_value)


def required_sample_size(probability: float, margin_of_error: float, alpha: float = 0.05) -> int:
    return calculate_sample_size(probability, margin_of_error, 1 - alpha).required_samples


@dataclass(frozen=True)
class SufficiencyThresholds:
    grade_a: float = 0.005
    grade_b: float = 0.010
    grade_c: float = 0.020

    def __post_init__(self) -> None:
        if not 0 < self.grade_a <= self.grade_b <= self.grade_c < 1:
            raise ValueError("样本评级阈值必须递增且位于 0 和 1 之间")


@dataclass(frozen=True)
class Sufficiency:
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
    thresholds = thresholds or SufficiencyThresholds()
    result = calculate_proportion(successes, total)
    rate = result.observed_rate or 0.0
    low, high = result.ci_low or 0.0, result.ci_high or 0.0
    width = high - low
    margin = width / 2
    planning_p = planning_probability if planning_probability is not None else rate
    plan = calculate_sample_size(planning_p, target_margin, current_samples=total)
    if total == 0 or margin > thresholds.grade_c:
        grade, label = "D", "样本不足"
    elif margin <= thresholds.grade_a:
        grade, label = "A", "非常可靠"
    elif margin <= thresholds.grade_b:
        grade, label = "B", "可用"
    else:
        grade, label = "C", "初步结果"
    return Sufficiency(
        total, rate, low, high, width, margin, plan.required_samples,
        plan.remaining_samples, grade, label,
    )


def session_probability_at_least_one(probability: float, searches: int) -> float:
    return calculate_session_probability(probability, searches).at_least_one
