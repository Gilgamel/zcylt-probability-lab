"""Tests for simulation and probability fitting."""

import numpy as np
import pytest

from services.estimator import fit_probability
from services.simulator import (
    CategoricalSimulator,
    ProductionSimulator,
    literal_horse_probabilities,
    normalized_probabilities,
    simulate_mixed_sessions,
)


def test_simulator_shape_and_expected_mean() -> None:
    result = ProductionSimulator(0.1, 20, 100_000, seed=7).simulate()
    assert result.shape == (100_000,)
    assert result.mean() == pytest.approx(2.0, abs=0.03)


def test_period_simulation_scales_trials() -> None:
    result = ProductionSimulator(0.1, 10, 1000, seed=1).simulate_month(2, 30)
    assert result.mean() == pytest.approx(60, abs=1)


def test_fit_probability_finds_nearby_candidate() -> None:
    observations = np.random.default_rng(9).binomial(18, 0.04, 5000)
    ranked = fit_probability(observations, 18, 0.02, 0.06, 0.005, 20_000)
    assert ranked.iloc[0]["probability"] == pytest.approx(0.04, abs=0.01)


def test_horse_literal_mode_preserves_99_percent_and_adds_other() -> None:
    displayed = {"GREEN": 0.41, "BLUE": 0.50, "PURPLE": 0.07, "ORANGE": 0.01}
    literal = literal_horse_probabilities(displayed)
    assert displayed == {"GREEN": 0.41, "BLUE": 0.50, "PURPLE": 0.07, "ORANGE": 0.01}
    assert literal["OTHER"] == pytest.approx(0.01)
    assert sum(literal.values()) == pytest.approx(1.0)


def test_normalization_is_explicit_and_reproducible() -> None:
    displayed = {"GREEN": 0.41, "BLUE": 0.50, "PURPLE": 0.07, "ORANGE": 0.01}
    normalized = normalized_probabilities(displayed)
    first = CategoricalSimulator(normalized, 8, 10_000, seed=42).simulate()
    second = CategoricalSimulator(normalized, 8, 10_000, seed=42).simulate()
    assert np.array_equal(first, second)
    assert normalized["ORANGE"] == pytest.approx(0.01 / 0.99)
    assert np.all(first.sum(axis=1) == 8)


def test_mixed_session_simulation_uses_actual_sizes_reproducibly() -> None:
    sizes = np.array([1, 4, 8])
    first = simulate_mixed_sessions(0.01, sizes, 10_000, seed=9)
    second = simulate_mixed_sessions(0.01, sizes, 10_000, seed=9)
    assert np.array_equal(first, second)
    assert first.mean() == pytest.approx(sizes.mean() * 0.01, abs=0.01)
