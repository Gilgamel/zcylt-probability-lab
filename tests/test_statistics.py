"""Tests for statistics services."""

import pytest

from services.statistics import (
    binomial_test,
    calculate_drop_rate,
    confidence_interval,
    proportion_z_test,
    sample_sufficiency,
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
