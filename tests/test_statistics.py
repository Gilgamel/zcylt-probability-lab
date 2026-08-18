"""Tests for statistics services."""

from math import ceil, comb, sqrt
from statistics import NormalDist

import numpy as np
import pytest
from scipy.stats import binom, binomtest, chisquare, fisher_exact

from services.statistics import (
    apply_holm_correction,
    binomial_test,
    calculate_binomial_test,
    calculate_chi_square_gof,
    calculate_drop_rate,
    calculate_margin_of_error,
    calculate_observed_rate,
    calculate_proportion,
    calculate_sample_size,
    calculate_session_probability,
    calculate_two_proportion_test,
    calculate_wilson_ci,
    classify_sample_quality,
    confidence_interval,
    chi_square_goodness_of_fit,
    proportion_z_test,
    sample_sufficiency,
    session_probability_at_least_one,
    interpret_p_value,
)


def _reference_wilson(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Independent Wilson formula, not the implementation's statsmodels call."""
    z_score = NormalDist().inv_cdf(0.5 + confidence / 2)
    observed = successes / trials
    denominator = 1 + z_score**2 / trials
    center = (observed + z_score**2 / (2 * trials)) / denominator
    half_width = z_score * sqrt(
        observed * (1 - observed) / trials + z_score**2 / (4 * trials**2)
    ) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def test_rate_and_wilson_interval() -> None:
    assert calculate_drop_rate(3, 100) == pytest.approx(0.03)
    low, high = confidence_interval(3, 100)
    assert 0 < low < 0.03 < high < 0.15


def test_empty_statistics_are_safe() -> None:
    assert calculate_drop_rate(0, 0) == 0
    assert confidence_interval(0, 0) == (0, 0)
    assert sample_sufficiency(0, 0).grade == "D"


def test_hypothesis_tests_return_probabilities() -> None:
    assert 0 <= binomial_test(3, 100, 0.03) <= 1
    _, p_value = proportion_z_test(3, 100, 6, 200)
    assert 0 <= p_value <= 1


def test_goodness_of_fit_and_dynamic_session_probability() -> None:
    statistic, p_value = chi_square_goodness_of_fit([410, 500, 70, 10, 10], [0.41, 0.5, 0.07, 0.01, 0.01])
    assert statistic == pytest.approx(0)
    assert p_value == pytest.approx(1)
    assert session_probability_at_least_one(0.01, 8) == pytest.approx(1 - 0.99**8)


@pytest.mark.parametrize("successes,trials,expected", [(0, 10, 0), (1, 4, 0.25), (50, 100, 0.5), (100, 100, 1)])
def test_observed_rate_boundaries(successes: int, trials: int, expected: float) -> None:
    assert calculate_observed_rate(successes, trials) == pytest.approx(expected)


def test_observed_rate_no_data_is_none() -> None:
    assert calculate_observed_rate(0, 0) is None
    assert calculate_wilson_ci(0, 0) == (None, None)


@pytest.mark.parametrize("successes,trials", [(-1, 2), (3, 2), (1, -1)])
def test_invalid_binomial_counts_rejected(successes: int, trials: int) -> None:
    with pytest.raises(ValueError):
        calculate_observed_rate(successes, trials)


def test_wilson_interval_contains_observed_rate() -> None:
    result = calculate_proportion(7, 100)
    assert result.ci_low < result.observed_rate < result.ci_high
    assert calculate_margin_of_error(result) == pytest.approx(result.ci_width / 2)


def test_wilson_all_failures_and_all_successes_are_bounded() -> None:
    zero = calculate_proportion(0, 10)
    all_success = calculate_proportion(10, 10)
    assert zero.ci_low == pytest.approx(0)
    assert 0 < zero.ci_high < 1
    assert 0 < all_success.ci_low < 1
    assert all_success.ci_high == pytest.approx(1)


@pytest.mark.parametrize(
    "successes,trials",
    [(0, 10), (1, 10), (5, 500), (10, 1000), (50, 5000), (10, 10)],
)
def test_wilson_matches_independent_reference(successes: int, trials: int) -> None:
    expected_low, expected_high = _reference_wilson(successes, trials)
    actual_low, actual_high = calculate_wilson_ci(successes, trials)
    assert actual_low == pytest.approx(expected_low, abs=1e-14)
    assert actual_high == pytest.approx(expected_high, abs=1e-14)
    rate = successes / trials
    assert 0 <= actual_low <= rate <= actual_high <= 1


def test_exact_binomial_detects_clear_difference() -> None:
    result = calculate_binomial_test(20, 100, 0.01)
    assert result.test_name == "Exact binomial test"
    assert result.significant


def test_exact_binomial_non_significant_at_target() -> None:
    assert not calculate_binomial_test(10, 100, 0.10).significant


@pytest.mark.parametrize(
    "successes,trials,target",
    [(1, 100, 0.01), (0, 10, 0.01), (5, 100, 0.01), (10, 100, 0.10)],
)
def test_exact_binomial_matches_scipy_reference(
    successes: int, trials: int, target: float
) -> None:
    actual = calculate_binomial_test(successes, trials, target)
    assert actual.p_value == pytest.approx(
        binomtest(successes, trials, target, alternative="two-sided").pvalue
    )


def test_two_proportion_uses_fisher_for_sparse_data() -> None:
    result = calculate_two_proportion_test(0, 10, 2, 10)
    assert result.test.test_name == "Fisher exact test"
    assert result.percentage_point_difference == pytest.approx(-20)
    reference = fisher_exact([[0, 10], [2, 8]], alternative="two-sided")
    assert result.test.p_value == pytest.approx(reference.pvalue)


@pytest.mark.parametrize(
    "first,second",
    [((0, 10), (0, 10)), ((1, 10), (1, 10)), ((1, 100), (5, 100))],
)
def test_sparse_two_proportion_tables_match_fisher_reference(first, second) -> None:
    result = calculate_two_proportion_test(*first, *second)
    table = [[first[0], first[1] - first[0]], [second[0], second[1] - second[0]]]
    assert result.test.test_name == "Fisher exact test"
    assert result.test.p_value == pytest.approx(fisher_exact(table).pvalue)


def test_two_proportion_uses_z_test_for_large_data() -> None:
    result = calculate_two_proportion_test(100, 1000, 150, 1000)
    assert result.test.test_name == "Two-proportion z-test"
    assert result.absolute_difference == pytest.approx(-0.05)


def test_holm_adjustment_never_reduces_p_values() -> None:
    comparisons = [
        calculate_two_proportion_test(10, 100, 30, 100),
        calculate_two_proportion_test(10, 100, 20, 100),
        calculate_two_proportion_test(10, 100, 11, 100),
    ]
    adjusted = apply_holm_correction(comparisons)
    assert all(item.adjusted_p_value >= item.test.p_value for item in adjusted)


def test_holm_matches_manual_reference_and_custom_alpha() -> None:
    comparisons = [
        calculate_two_proportion_test(10, 100, 30, 100),
        calculate_two_proportion_test(10, 100, 20, 100),
        calculate_two_proportion_test(10, 100, 11, 100),
        calculate_two_proportion_test(10, 100, 15, 100),
    ]
    corrected = apply_holm_correction(comparisons, alpha=0.01)
    raw = np.asarray([item.test.p_value for item in comparisons])
    order = np.argsort(raw)
    sorted_adjusted = np.maximum.accumulate(
        [(len(raw) - rank) * raw[index] for rank, index in enumerate(order)]
    ).clip(0, 1)
    manual = np.empty(len(raw))
    manual[order] = sorted_adjusted
    assert [item.adjusted_p_value for item in corrected] == pytest.approx(manual)
    assert all(item.test.alpha == 0.01 for item in corrected)
    assert np.all(np.diff(manual[order]) >= 0)


def test_chi_square_structured_result() -> None:
    result = calculate_chi_square_gof([410, 500, 70, 10, 10], [0.41, 0.50, 0.07, 0.01, 0.01])
    assert result.statistic == pytest.approx(0)
    assert result.degrees_of_freedom == 4
    assert all(value == pytest.approx(0) for value in result.residuals)


def test_chi_square_matches_manual_and_scipy_reference() -> None:
    observed = np.asarray([30, 20, 25, 25])
    expected = np.full(4, 25.0)
    manual_statistic = float(np.sum((observed - expected) ** 2 / expected))
    scipy_result = chisquare(observed, expected)
    result = calculate_chi_square_gof(observed.tolist(), [0.25] * 4)
    assert result.statistic == pytest.approx(manual_statistic)
    assert result.statistic == pytest.approx(scipy_result.statistic)
    assert result.p_value == pytest.approx(scipy_result.pvalue)
    assert result.expected == pytest.approx(expected)


def test_chi_square_rejects_small_expected_counts() -> None:
    with pytest.raises(ValueError, match="小于 5"):
        calculate_chi_square_gof([8, 1, 1], [0.8, 0.1, 0.1])


@pytest.mark.parametrize("probability,margin,expected", [(0.5, 0.05, 385), (0.01, 0.01, 381), (0.0, 0.05, 385)])
def test_sample_size_planning(probability: float, margin: float, expected: int) -> None:
    assert calculate_sample_size(probability, margin).required_samples == expected


def test_sample_size_remaining_never_negative() -> None:
    plan = calculate_sample_size(0.5, 0.05, current_samples=1000)
    assert plan.remaining_samples == 0


@pytest.mark.parametrize(
    "probability,margin,expected",
    [(0.01, 0.005, 1522), (0.05, 0.01, 1825), (0.50, 0.05, 385)],
)
def test_sample_size_matches_independent_formula(
    probability: float, margin: float, expected: int
) -> None:
    z_score = NormalDist().inv_cdf(0.975)
    manual = ceil(z_score**2 * probability * (1 - probability) / margin**2)
    assert manual == expected
    assert calculate_sample_size(probability, margin).required_samples == expected


def test_session_probabilities_are_exact_and_sum_consistently() -> None:
    result = calculate_session_probability(0.01, 8)
    assert result.zero == pytest.approx(0.99**8)
    assert result.exactly_one == pytest.approx(8 * 0.01 * 0.99**7)
    assert result.at_least_one == pytest.approx(1 - result.zero)
    assert 0 < result.at_least_two < result.at_least_one
    probabilities = [
        comb(8, k) * 0.01**k * 0.99 ** (8 - k) for k in range(9)
    ]
    assert sum(probabilities) == pytest.approx(1)
    assert result.zero == pytest.approx(binom.pmf(0, 8, 0.01))
    assert result.exactly_one == pytest.approx(binom.pmf(1, 8, 0.01))
    assert result.at_least_two == pytest.approx(sum(probabilities[2:]))


def test_sample_quality_labels() -> None:
    assert classify_sample_quality(calculate_proportion(0, 0)) == "No Data"
    assert classify_sample_quality(calculate_proportion(1, 10)) == "Very Low"
    assert classify_sample_quality(calculate_proportion(10, 100)) in {"Low", "Moderate"}
    assert classify_sample_quality(calculate_proportion(5000, 10000)) == "Good"


def test_one_percent_at_n100_is_not_strong() -> None:
    result = calculate_proportion(1, 100)
    assert result.observed_rate == pytest.approx(0.01)
    assert result.ci_width > 0.05
    assert classify_sample_quality(result) == "Moderate"


def test_hypothesis_language_never_accepts_null() -> None:
    assert "反对" in interpret_p_value(0.01, "目标概率")
    non_significant = interpret_p_value(0.50, "目标概率")
    assert "证据不足以拒绝" in non_significant
    assert "不等于证明" in non_significant
