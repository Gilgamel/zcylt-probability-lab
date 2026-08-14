"""Tests for statistics services."""

import pytest

from services.statistics import (
    binomial_test,
    calculate_drop_rate,
    confidence_interval,
    chi_square_goodness_of_fit,
    proportion_z_test,
    sample_sufficiency,
    session_probability_at_least_one,
)


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
