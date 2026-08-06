"""Tests for simulation and probability fitting."""

import numpy as np
import pytest

from services.estimator import fit_probability
from services.simulator import ProductionSimulator


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
