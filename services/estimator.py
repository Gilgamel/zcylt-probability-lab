"""Monte Carlo probability fitting and candidate ranking."""

import numpy as np
import pandas as pd


def fit_binary_probability(
    successes: int,
    total_trials: int,
    probability_min: float,
    probability_max: float,
    step: float,
    iterations: int,
    seed: int = 42,
    displayed_probability: float | None = None,
) -> pd.DataFrame:
    """Rank Bernoulli candidates using simulated rate error.

    The observed rate remains the direct maximum-likelihood estimate. This
    simulation ranking is a model-validation aid rather than a replacement.
    """
    if total_trials <= 0 or not 0 <= successes <= total_trials:
        raise ValueError("成功数或总样本量无效")
    if step <= 0 or probability_min > probability_max:
        raise ValueError("概率范围或步长无效")
    if iterations <= 0:
        raise ValueError("迭代次数必须大于 0")
    candidates = np.arange(probability_min, probability_max + step / 2, step)
    if np.any((candidates < 0) | (candidates > 1)):
        raise ValueError("候选概率必须在 0 和 1 之间")
    observed_rate = successes / total_trials
    rows: list[dict[str, float | bool]] = []
    for index, probability in enumerate(candidates):
        rng = np.random.default_rng(seed + index)
        simulated_rates = rng.binomial(total_trials, probability, iterations) / total_trials
        simulated_rate = float(simulated_rates.mean())
        rows.append({
            "probability": float(probability),
            "simulated_probability": simulated_rate,
            "error_score": abs(simulated_rate - observed_rate),
            "is_displayed_probability": bool(
                displayed_probability is not None
                and np.isclose(probability, displayed_probability, atol=step / 2)
            ),
        })
    frame = pd.DataFrame(rows).sort_values(
        ["error_score", "probability"], kind="stable"
    ).reset_index(drop=True)
    frame["rank"] = np.arange(1, len(frame) + 1)
    return frame


def fit_probability(
    observations: np.ndarray,
    quantity: int,
    probability_min: float,
    probability_max: float,
    step: float,
    iterations: int,
    seed: int = 42,
) -> pd.DataFrame:
    """Backward-compatible fitting API for equal-size observed batches."""
    if observations.size == 0 or quantity <= 0:
        raise ValueError("没有可用于拟合的真实数据")
    frame = fit_binary_probability(
        int(observations.sum()),
        int(observations.size * quantity),
        probability_min,
        probability_max,
        step,
        iterations,
        seed,
    )
    frame["simulated_mean"] = frame["simulated_probability"] * quantity
    return frame
