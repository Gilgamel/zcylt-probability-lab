"""Tests for presentation-ready analysis transforms and Phase 3 charts."""

import pandas as pd
import plotly.graph_objects as go
import pytest

from charts.statistical_charts import (
    cumulative_rate_chart, observed_vs_target_chart, quality_distribution_chart,
    rate_with_ci_chart,
)
from services.analysis import (
    aggregate_proportion, comparison_table, complete_level_table, cumulative_daily,
    dashboard_daily_metrics, pairwise_level_comparisons, proportion_table,
    quality_distribution, session_summary,
    species_distribution,
)
from services.statistics import apply_holm_correction, calculate_two_proportion_test


def test_aggregate_proportion_empty_is_no_data() -> None:
    result = aggregate_proportion(pd.DataFrame(columns=["attempts", "orange"]))
    assert result.observed_rate is None


def test_complete_level_table_includes_no_data_levels() -> None:
    frame = pd.DataFrame([{"level": 10, "attempts": 100, "orange": 3}])
    result = complete_level_table(frame)
    assert result["level"].tolist() == [9, 10, 11, 12]
    assert result.loc[result["level"] == 9, "sample_quality"].item() == "No Data"
    assert pd.isna(result.loc[result["level"] == 9, "rate"].item())


def test_cumulative_daily_uses_weighted_raw_counts() -> None:
    frame = pd.DataFrame([
        {"date": pd.Timestamp("2026-01-01"), "attempts": 10, "orange": 1},
        {"date": pd.Timestamp("2026-01-02"), "attempts": 90, "orange": 0},
    ])
    result = cumulative_daily(frame)
    assert result.iloc[-1]["rate"] == pytest.approx(0.01)
    assert result["daily_rate"].tolist() == pytest.approx([0.1, 0.0])
    assert result.iloc[-1]["cumulative_attempts"] == 100


def test_dashboard_metrics_are_grouped_by_category() -> None:
    frame = pd.DataFrame([
        {"date": "2026-01-01", "category": "A", "category_type": "A", "attempt_count": 10, "orange_count": 1},
        {"date": "2026-01-01", "category": "B", "category_type": "B", "attempt_count": 5, "orange_count": 1},
        {"date": "2026-01-02", "category": "A", "category_type": "A", "attempt_count": 20, "orange_count": 1},
    ])
    result = dashboard_daily_metrics(frame)
    assert result["sample_growth"].tolist() == [10, 5, 30, 5]
    category_b = result[result["category"] == "B"]
    assert category_b["attempt_count"].tolist() == [5, 0]
    assert category_b["sample_growth"].tolist() == [5, 5]
    assert pd.isna(category_b.iloc[-1]["observed_probability"])


def test_level_comparisons_only_use_available_pairs() -> None:
    frame = pd.DataFrame([
        {"level": 9, "attempts": 100, "orange": 1},
        {"level": 10, "attempts": 100, "orange": 10},
        {"level": 12, "attempts": 100, "orange": 20},
    ])
    comparisons = pairwise_level_comparisons(frame)
    assert [(item.label_a, item.label_b) for item in comparisons] == [("9", "10"), ("9", "12")]
    assert all(item.adjusted_p_value is not None for item in comparisons)


def test_comparison_table_has_raw_and_holm_p() -> None:
    source = pd.DataFrame([
        {"level": 9, "attempts": 100, "orange": 1},
        {"level": 10, "attempts": 100, "orange": 10},
    ])
    table = comparison_table(pairwise_level_comparisons(source))
    assert {"raw_p", "holm_p", "percentage_point_difference"}.issubset(table.columns)


def test_comparison_table_reports_actual_mixed_test_methods() -> None:
    comparisons = apply_holm_correction([
        calculate_two_proportion_test(0, 10, 2, 10),
        calculate_two_proportion_test(100, 1000, 150, 1000),
    ])
    table = comparison_table(comparisons)
    assert set(table["test"]) == {"Fisher exact test", "Two-proportion z-test"}
    assert table["holm_p"].notna().all()


def test_quality_distribution_includes_unaccounted_and_targets() -> None:
    summary = pd.DataFrame([{"attempts": 100, "green": 41, "blue": 50, "purple": 7, "orange": 1, "unaccounted": 1}])
    result = quality_distribution(summary, {"GREEN": 0.41, "ORANGE": 0.01})
    assert result["count"].sum() == 100
    assert result.loc[result["quality_key"] == "green", "target"].item() == pytest.approx(0.41)
    assert result.loc[result["quality_key"] == "unaccounted", "target"].isna().item()


def test_species_distribution_has_real_wilson_intervals() -> None:
    frame = pd.DataFrame([
        {"item": "A", "attempts": 40},
        {"item": "B", "attempts": 30},
        {"item": "C", "attempts": 20},
        {"item": "D", "attempts": 10},
    ])
    result = species_distribution(frame, ("A", "B", "C", "D"))
    assert result["observed_rate"].tolist() == pytest.approx([0.4, 0.3, 0.2, 0.1])
    assert all(result["ci_low"] < result["observed_rate"])
    assert all(result["ci_high"] > result["observed_rate"])
    assert not any(result["ci_low"] == result["ci_high"])


def test_proportion_table_calculates_wilson_per_group() -> None:
    frame = pd.DataFrame([{"item": "A", "attempts": 100, "orange": 10}])
    result = proportion_table(frame, "item")
    assert result.iloc[0]["rate"] == pytest.approx(0.1)
    assert result.iloc[0]["ci_low"] < 0.1 < result.iloc[0]["ci_high"]


def test_session_summary_empty_and_measured() -> None:
    empty = session_summary(pd.DataFrame(columns=["searches", "orange"]))
    assert empty["average_searches"] is None
    measured = session_summary(pd.DataFrame([{"searches": 8, "orange": 0}, {"searches": 4, "orange": 2}]))
    assert measured == {"sessions": 2, "searches": 12, "average_searches": 6.0, "zero_orange": 1, "one_or_more": 1, "two_or_more": 1}


@pytest.mark.parametrize("factory", [cumulative_rate_chart, quality_distribution_chart])
def test_empty_charts_return_figures(factory) -> None:
    if factory is quality_distribution_chart:
        figure = factory(pd.DataFrame(), "empty")
    else:
        figure = factory(pd.DataFrame())
    assert isinstance(figure, go.Figure)


def test_all_required_statistical_charts_are_plotly_figures() -> None:
    cumulative = pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "rate": 0.1}])
    rates = pd.DataFrame([{"group": "A", "rate": 0.1, "ci_low": 0.05, "ci_high": 0.2}])
    qualities = pd.DataFrame([{"quality": "橙品", "rate": 0.01, "target": 0.01}])
    figures = [
        cumulative_rate_chart(cumulative), rate_with_ci_chart(rates, "group"),
        quality_distribution_chart(qualities, "quality"),
        observed_vs_target_chart(qualities, "target"),
    ]
    assert all(isinstance(figure, go.Figure) and figure.data for figure in figures)
