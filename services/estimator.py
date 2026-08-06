"""Probability fitting by simulated distribution distance."""

import numpy as np
import pandas as pd


def fit_probability(
    observations: np.ndarray,
    quantity: int,
    probability_min: float,
    probability_max: float,
    step: float,
    iterations: int,
    seed: int = 42,
) -> pd.DataFrame:
    """Rank probability candidates by mean and variance error."""
    if observations.size == 0:
        raise ValueError("没有可用于拟合的真实数据")
    if step <= 0 or probability_min > probability_max:
        raise ValueError("概率范围或步长无效")
    target_mean = float(np.mean(observations))
    target_var = float(np.var(observations))
    probabilities = np.arange(probability_min, probability_max + step / 2, step)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float]] = []
    for probability in probabilities:
        simulated = rng.binomial(quantity, probability, iterations)
        mean_error = abs(float(simulated.mean()) - target_mean) / max(quantity, 1)
        variance_error = abs(float(simulated.var()) - target_var) / max(quantity, 1)
        rows.append({
            "probability": float(probability),
            "error_score": mean_error + variance_error,
            "simulated_mean": float(simulated.mean()),
        })
    return pd.DataFrame(rows).sort_values("error_score").reset_index(drop=True)
