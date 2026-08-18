"""Statistical, reproducibility, storage, and performance tests for Phase 4."""

import numpy as np
import pytest
from scipy.stats import binom

from charts.monte_carlo_charts import (
    binary_count_distribution_chart,
    binary_rate_distribution_chart,
    multinomial_comparison_chart,
    session_distribution_chart,
)
from services.monte_carlo import (
    BIRD_EQUAL_SPECIES_MODEL,
    MAX_SEED,
    MAX_SIMULATIONS,
    MAX_TRIALS,
    binary_summary_frame,
    multinomial_summary_frame,
    session_probability_frame,
    simulate_binary,
    simulate_multinomial,
)
from services.simulator import literal_horse_probabilities


@pytest.mark.parametrize("probability", [0.0, 0.01, 0.5, 1.0])
def test_binary_shape_bounds_and_expected_mean(probability: float) -> None:
    result = simulate_binary(probability, 10_000, 100_000, 73)
    assert result.samples.shape == (100_000,)
    assert np.all((result.samples >= 0) & (result.samples <= 10_000))
    assert result.outcome.mean == pytest.approx(10_000 * probability, abs=0.2)


@pytest.mark.parametrize(
    ("simulations", "tolerance"),
    [(10_000, 0.35), (100_000, 0.15), (500_000, 0.07)],
)
def test_rare_event_convergence_at_required_scales(simulations: int, tolerance: float) -> None:
    result = simulate_binary(0.01, 10_000, simulations, 20260817)
    assert result.outcome.mean == pytest.approx(100.0, abs=tolerance)
    assert result.outcome.std == pytest.approx(np.sqrt(99), abs=0.08)


def test_same_seed_is_exactly_reproducible_and_other_seed_differs() -> None:
    first = simulate_binary(0.03, 200, 10_000, 7)
    second = simulate_binary(0.03, 200, 10_000, 7)
    third = simulate_binary(0.03, 200, 10_000, 8)
    assert np.array_equal(first.samples, second.samples)
    assert not np.array_equal(first.samples, third.samples)


def test_automatic_seed_is_recorded_and_replayable() -> None:
    generated = simulate_binary(0.03, 200, 10_000, None)
    replay = simulate_binary(0.03, 200, 10_000, generated.random_seed)
    assert 0 <= generated.random_seed <= MAX_SEED
    assert np.array_equal(generated.samples, replay.samples)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"trial_count": 0}, "trial_count"),
        ({"trial_count": MAX_TRIALS + 1}, "trial_count"),
        ({"trial_count": True}, "trial_count"),
        ({"simulation_count": 0}, "simulation_count"),
        ({"simulation_count": MAX_SIMULATIONS + 1}, "simulation_count"),
        ({"simulation_count": True}, "simulation_count"),
        ({"seed": -1}, "随机种子"),
        ({"seed": MAX_SEED + 1}, "随机种子"),
        ({"seed": True}, "随机种子"),
    ],
)
def test_binary_limits_are_enforced(kwargs: dict, message: str) -> None:
    values = {"target_probability": 0.1, "trial_count": 10, "simulation_count": 100, "seed": 1}
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        simulate_binary(**values)


def test_binary_summary_quantiles_intervals_and_actual_comparison() -> None:
    result = simulate_binary(0.1, 100, 100_000, 19, actual_successes=16, actual_trials=100)
    summary = result.outcome
    assert list(summary.quantiles) == ["p01", "p05", "p25", "p50", "p75", "p95", "p99"]
    assert summary.quantiles["p05"] <= summary.median <= summary.quantiles["p95"]
    assert summary.simulation_interval == tuple(np.quantile(result.samples, [0.025, 0.975]))
    assert summary.simulation_interval_99 == tuple(np.quantile(result.samples, [0.005, 0.995]))
    assert summary.simulation_interval_99[0] <= summary.simulation_interval[0]
    assert summary.simulation_interval_99[1] >= summary.simulation_interval[1]
    assert summary.actual_percentile == pytest.approx(np.mean(result.samples <= 16))
    assert 0 <= summary.actual_percentile <= 1
    expected_tail = (np.count_nonzero(np.abs(result.samples - 10) >= 6) + 1) / 100_001
    assert summary.empirical_tail_probability == pytest.approx(expected_tail)
    assert summary.difference_from_expected == pytest.approx(6)
    assert summary.standardized_difference == pytest.approx(2.0)
    assert summary.classification in {
        "Consistent with the theoretical model",
        "Unusual under the theoretical model",
        "Very unusual under the theoretical model",
    }


def test_mismatched_actual_size_is_retained_but_not_directly_compared() -> None:
    result = simulate_binary(0.1, 100, 10_000, 2, actual_successes=8, actual_trials=80)
    assert result.outcome.actual_count == 8
    assert result.actual_rate == pytest.approx(0.1)
    assert result.outcome.actual_percentile is None
    assert result.outcome.empirical_tail_probability is None
    assert result.outcome.classification == "No actual observation comparison"


def test_binary_storage_is_versioned_json_safe_and_excludes_samples() -> None:
    result = simulate_binary(0.2, 20, 10_000, 5)
    payload = result.storage_dict()
    assert payload["result_version"] == 1
    assert payload["model_type"] == "binomial"
    assert payload["seed"] == 5
    assert "samples" not in payload
    assert "simulation_interval" in payload


def test_horse_literal_multinomial_preserves_displayed_values_and_remainder() -> None:
    displayed = {"GREEN": 0.41, "BLUE": 0.50, "PURPLE": 0.07, "ORANGE": 0.01}
    model = literal_horse_probabilities(displayed)
    result = simulate_multinomial(model, 8, 100_000, 11)
    assert result.probabilities == pytest.approx((0.41, 0.50, 0.07, 0.01, 0.01))
    assert np.all(result.samples.sum(axis=1) == 8)
    assert result.per_category["ORANGE"].mean == pytest.approx(0.08, abs=0.004)
    assert result.per_category["OTHER"].mean == pytest.approx(0.08, abs=0.004)


@pytest.mark.parametrize(
    "model",
    [
        {"BLUE": 0.79, "PURPLE": 0.20, "ORANGE": 0.01},
        {"铁羽雁": 0.25, "九炎鹊": 0.25, "出云鹤": 0.25, "暗铁鸦": 0.25},
    ],
)
def test_bird_multinomial_models_converge(model: dict[str, float]) -> None:
    result = simulate_multinomial(model, 1_000, 100_000, 31)
    means = result.samples.mean(axis=0) / 1_000
    assert means == pytest.approx(tuple(model.values()), abs=0.0003)
    assert sum(result.probabilities) == pytest.approx(1.0)


def test_bird_species_model_name_is_explicitly_nonofficial_hypothesis() -> None:
    assert BIRD_EQUAL_SPECIES_MODEL == "equal_25_percent_hypothesis"


def test_multinomial_actual_comparison_and_storage() -> None:
    model = {"A": 0.25, "B": 0.75}
    result = simulate_multinomial(
        model, 20, 10_000, 4, actual_counts={"A": 7, "B": 13}, actual_trials=20
    )
    assert result.actual_comparable
    assert result.per_category["A"].actual_percentile is not None
    payload = result.storage_dict()
    assert payload["result_version"] == 1
    assert payload["model_type"] == "multinomial"
    assert "samples" not in payload
    assert "per_category_summary" in payload
    assert payload["actual_percentiles"]["A"] == result.per_category["A"].actual_percentile
    assert payload["simulation_intervals"]["A"] == list(
        result.per_category["A"].simulation_interval
    )


@pytest.mark.parametrize(
    "model",
    [{"A": 0.4, "B": 0.5}, {"A": -0.1, "B": 1.1}, {"A": 1.0}],
)
def test_multinomial_rejects_invalid_models_without_normalizing(model: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        simulate_multinomial(model, 10, 100, 1)


def test_multinomial_rejects_incomplete_or_inconsistent_actual_counts() -> None:
    with pytest.raises(ValueError, match="类别"):
        simulate_multinomial(
            {"A": 0.5, "B": 0.5}, 10, 100, 1,
            actual_counts={"A": 5}, actual_trials=5,
        )
    with pytest.raises(ValueError, match="合计"):
        simulate_multinomial(
            {"A": 0.5, "B": 0.5}, 10, 100, 1,
            actual_counts={"A": 4, "B": 4}, actual_trials=10,
        )


def test_horse_session_simulation_matches_exact_binomial() -> None:
    result = simulate_binary(0.01, 8, 500_000, 17)
    frame = session_probability_frame(result, [0, 0, 1])
    assert frame["exact_probability"].sum() == pytest.approx(1.0)
    assert frame.loc[0, "exact_probability"] == pytest.approx(binom.pmf(0, 8, 0.01))
    assert frame.loc[1, "actual_probability"] == pytest.approx(1 / 3)
    assert np.max(np.abs(frame["simulated_probability"] - frame["exact_probability"])) < 0.001


def test_summary_frames_and_charts_are_constructible() -> None:
    binary = simulate_binary(0.1, 50, 10_000, 2)
    multi = simulate_multinomial({"A": 0.3, "B": 0.7}, 50, 10_000, 2)
    session = session_probability_frame(simulate_binary(0.01, 8, 10_000, 2))
    binary_frame = binary_summary_frame(binary)
    multinomial_frame = multinomial_summary_frame(multi)
    assert not binary_frame.empty
    assert {"interval_99_low", "interval_99_high"}.issubset(binary_frame.columns)
    assert len(multinomial_frame) == 2
    assert {"interval_99_low", "interval_99_high"}.issubset(multinomial_frame.columns)
    assert binary_count_distribution_chart(binary).data
    assert binary_rate_distribution_chart(binary).data
    assert multinomial_comparison_chart(multi).data
    assert session_distribution_chart(session).data
