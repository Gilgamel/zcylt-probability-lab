"""Transform compact SQL aggregates into presentation-ready Phase 3 results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from services.statistics import (
    ProportionComparisonResult,
    apply_holm_correction,
    calculate_proportion,
    calculate_two_proportion_test,
    classify_sample_quality,
)


QUALITY_KEYS = ("green", "blue", "purple", "orange", "unaccounted")
QUALITY_LABELS = {
    "green": "绿品", "blue": "蓝品", "purple": "紫品", "orange": "橙品",
    "unaccounted": "其他 / 未说明",
}


def aggregate_proportion(frame: pd.DataFrame, success_column: str = "orange", trial_column: str = "attempts"):
    """Calculate a proportion from already aggregated database rows."""
    if frame.empty:
        return calculate_proportion(0, 0)
    return calculate_proportion(
        int(frame[success_column].sum()), int(frame[trial_column].sum())
    )


def proportion_table(
    frame: pd.DataFrame,
    group_column: str,
    success_column: str = "orange",
    trial_column: str = "attempts",
) -> pd.DataFrame:
    """Add Wilson intervals and precision labels to grouped SQL results."""
    columns = [
        group_column, "successes", "trials", "rate", "ci_low", "ci_high",
        "ci_width", "sample_quality",
    ]
    rows: list[dict[str, object]] = []
    for row in frame.to_dict("records"):
        result = calculate_proportion(int(row[success_column]), int(row[trial_column]))
        rows.append({
            group_column: row[group_column],
            "successes": result.successes,
            "trials": result.trials,
            "rate": result.observed_rate,
            "ci_low": result.ci_low,
            "ci_high": result.ci_high,
            "ci_width": result.ci_width,
            "sample_quality": classify_sample_quality(result),
        })
    return pd.DataFrame(rows, columns=columns)


def complete_level_table(frame: pd.DataFrame, levels: Sequence[int] = (9, 10, 11, 12)) -> pd.DataFrame:
    """Produce one row per skill level, retaining explicit No Data states."""
    grouped = (
        frame.groupby("level", as_index=False)[["attempts", "orange"]].sum()
        if not frame.empty else pd.DataFrame(columns=["level", "attempts", "orange"])
    )
    by_level = {int(row["level"]): row for row in grouped.to_dict("records")}
    rows = []
    for level in levels:
        row = by_level.get(level, {"attempts": 0, "orange": 0})
        result = calculate_proportion(int(row["orange"]), int(row["attempts"]))
        rows.append({
            "level": level, "successes": result.successes, "trials": result.trials,
            "rate": result.observed_rate, "ci_low": result.ci_low,
            "ci_high": result.ci_high, "ci_width": result.ci_width,
            "sample_quality": classify_sample_quality(result),
        })
    return pd.DataFrame(rows)


def cumulative_daily(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate cumulative success rate from compact daily SQL aggregates."""
    columns = ["date", "attempts", "orange", "daily_rate", "cumulative_attempts", "cumulative_orange", "rate"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = frame.sort_values("date").copy()
    result["daily_rate"] = result["orange"] / result["attempts"]
    result["cumulative_attempts"] = result["attempts"].cumsum()
    result["cumulative_orange"] = result["orange"].cumsum()
    result["rate"] = result["cumulative_orange"] / result["cumulative_attempts"]
    return result[columns]


def dashboard_daily_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Add daily rates and a complete cumulative series for every category."""
    columns = list(frame.columns) + ["observed_probability", "sample_growth"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    all_dates = pd.date_range(result["date"].min(), result["date"].max(), freq="D")
    completed: list[pd.DataFrame] = []
    for (category, category_type), group in result.groupby(
        ["category", "category_type"], sort=False
    ):
        category_daily = (
            group.set_index("date")[["attempt_count", "orange_count"]]
            .reindex(all_dates, fill_value=0)
            .rename_axis("date")
            .reset_index()
        )
        category_daily["category"] = category
        category_daily["category_type"] = category_type
        category_daily["observed_probability"] = (
            category_daily["orange_count"] / category_daily["attempt_count"]
        ).where(category_daily["attempt_count"] > 0)
        category_daily["sample_growth"] = category_daily["attempt_count"].cumsum()
        completed.append(category_daily)
    return (
        pd.concat(completed, ignore_index=True)
        .sort_values(["date", "category"], kind="stable")
        .loc[:, columns]
        .reset_index(drop=True)
    )


def pairwise_level_comparisons(
    frame: pd.DataFrame,
    pairs: Sequence[tuple[int, int]] = ((9, 10), (10, 11), (11, 12), (9, 12)),
) -> list[ProportionComparisonResult]:
    grouped = (
        frame.groupby("level", as_index=False)[["attempts", "orange"]].sum()
        if not frame.empty else pd.DataFrame(columns=["level", "attempts", "orange"])
    )
    values = {
        int(row["level"]): (int(row["orange"]), int(row["attempts"]))
        for row in grouped.to_dict("records")
    }
    comparisons = []
    for first, second in pairs:
        if first not in values or second not in values:
            continue
        comparisons.append(calculate_two_proportion_test(
            *values[first], *values[second], label_a=str(first), label_b=str(second)
        ))
    return apply_holm_correction(comparisons)


def comparison_table(comparisons: Sequence[ProportionComparisonResult]) -> pd.DataFrame:
    columns = [
        "comparison", "rate_a", "rate_b", "absolute_difference",
        "percentage_point_difference", "test", "raw_p", "holm_p", "significant",
    ]
    return pd.DataFrame([{
        "comparison": f"{item.label_a} vs {item.label_b}",
        "rate_a": item.rate_a, "rate_b": item.rate_b,
        "absolute_difference": item.absolute_difference,
        "percentage_point_difference": item.percentage_point_difference,
        "test": item.test.test_name, "raw_p": item.test.p_value,
        "holm_p": item.adjusted_p_value,
        "significant": bool(item.adjusted_p_value is not None and item.adjusted_p_value < item.test.alpha),
    } for item in comparisons], columns=columns)


def quality_distribution(summary: pd.DataFrame, targets: Mapping[str, float] | None = None) -> pd.DataFrame:
    """Create quality counts, rates, Wilson CIs and optional displayed targets."""
    columns = ["quality_key", "quality", "count", "trials", "rate", "ci_low", "ci_high", "target"]
    if summary.empty:
        return pd.DataFrame(columns=columns)
    row = summary.iloc[0]
    trials = int(row["attempts"])
    target_map = {key.lower(): value for key, value in (targets or {}).items()}
    rows = []
    for key in QUALITY_KEYS:
        count = int(row.get(key, 0))
        result = calculate_proportion(count, trials)
        rows.append({
            "quality_key": key, "quality": QUALITY_LABELS[key], "count": count,
            "trials": trials, "rate": result.observed_rate,
            "ci_low": result.ci_low, "ci_high": result.ci_high,
            "target": target_map.get(key),
        })
    return pd.DataFrame(rows, columns=columns)


def species_distribution(frame: pd.DataFrame, species_names: Sequence[str]) -> pd.DataFrame:
    """Complete species counts and 25%-hypothesis diagnostics for display."""
    source = {str(row["item"]): row for row in frame.to_dict("records")}
    rows = [
        source.get(name, {"item": name, "records": 0, "attempts": 0, "green": 0, "blue": 0, "purple": 0, "orange": 0, "unaccounted": 0})
        for name in species_names
    ]
    result = pd.DataFrame(rows)
    total = int(result["attempts"].sum())
    if not total:
        result["observed_rate"] = None
        result["expected_count"] = None
        result["count_difference"] = None
        result["residual"] = None
        result["ci_low"] = None
        result["ci_high"] = None
        return result
    expected = total / len(species_names)
    result["observed_rate"] = result["attempts"] / total
    result["expected_count"] = expected
    result["count_difference"] = result["attempts"] - expected
    result["residual"] = result["count_difference"] / expected**0.5
    intervals = [
        calculate_proportion(int(count), total)
        for count in result["attempts"]
    ]
    result["ci_low"] = [item.ci_low for item in intervals]
    result["ci_high"] = [item.ci_high for item in intervals]
    return result


def session_summary(frame: pd.DataFrame) -> dict[str, float | int | None]:
    if frame.empty:
        return {"sessions": 0, "searches": 0, "average_searches": None, "zero_orange": 0, "one_or_more": 0, "two_or_more": 0}
    sessions = len(frame)
    return {
        "sessions": sessions,
        "searches": int(frame["searches"].sum()),
        "average_searches": float(frame["searches"].mean()),
        "zero_orange": int((frame["orange"] == 0).sum()),
        "one_or_more": int((frame["orange"] >= 1).sum()),
        "two_or_more": int((frame["orange"] >= 2).sum()),
    }
