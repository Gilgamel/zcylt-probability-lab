"""Plotly chart factories for Phase 4 Monte Carlo results."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from services.monte_carlo import BinaryMonteCarloResult, MultinomialMonteCarloResult


def binary_count_distribution_chart(
    result: BinaryMonteCarloResult, title: str = "模拟成功数量分布"
) -> go.Figure:
    figure = go.Figure(go.Histogram(x=result.samples, name="模拟数据集"))
    low, high = result.outcome.simulation_interval
    figure.add_vrect(x0=low, x1=high, opacity=0.15, line_width=0, annotation_text="95% 模拟区间")
    figure.add_vline(x=result.outcome.expected, line_dash="dash", annotation_text="模型期望")
    if result.actual_comparable:
        figure.add_vline(x=result.outcome.actual_count, line_dash="dot", annotation_text="实际数量")
    figure.update_layout(title=title, xaxis_title="成功数量", yaxis_title="模拟数据集频数")
    return figure


def binary_rate_distribution_chart(
    result: BinaryMonteCarloResult, title: str = "模拟成功率分布"
) -> go.Figure:
    rates = result.samples / result.trial_count
    low, high = result.outcome.simulation_interval
    figure = go.Figure(go.Histogram(x=rates, name="模拟数据集"))
    figure.add_vrect(
        x0=low / result.trial_count,
        x1=high / result.trial_count,
        opacity=0.15,
        line_width=0,
        annotation_text="95% 模拟区间",
    )
    figure.add_vline(
        x=result.target_probability,
        line_dash="dash",
        annotation_text="目标概率",
    )
    if result.actual_comparable and result.actual_rate is not None:
        figure.add_vline(x=result.actual_rate, line_dash="dot", annotation_text="实际观测率")
    figure.update_layout(
        title=title,
        xaxis_title="成功率",
        yaxis_title="模拟数据集频数",
        xaxis_tickformat=".2%",
    )
    return figure


def multinomial_comparison_chart(
    result: MultinomialMonteCarloResult,
    title: str = "实际数量与模拟分布比较",
) -> go.Figure:
    categories = list(result.categories)
    expected = np.asarray([result.per_category[key].expected for key in categories])
    low = np.asarray([result.per_category[key].simulation_interval[0] for key in categories])
    high = np.asarray([result.per_category[key].simulation_interval[1] for key in categories])
    figure = go.Figure()
    figure.add_scatter(
        x=categories,
        y=expected,
        mode="markers",
        name="模型期望",
        error_y={
            "type": "data",
            "symmetric": False,
            "array": high - expected,
            "arrayminus": expected - low,
        },
    )
    if result.actual_comparable and result.actual_counts is not None:
        figure.add_scatter(
            x=categories,
            y=[result.actual_counts[key] for key in categories],
            mode="markers",
            name="实际数量",
            marker={"size": 11},
        )
    figure.update_layout(title=title, xaxis_title="类别", yaxis_title="数量")
    return figure


def session_distribution_chart(frame: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_bar(x=frame["successes"], y=frame["simulated_probability"], name="Monte Carlo")
    figure.add_scatter(x=frame["successes"], y=frame["exact_probability"], name="精确二项", mode="lines+markers")
    if frame["actual_probability"].notna().any():
        figure.add_scatter(x=frame["successes"], y=frame["actual_probability"], name="实际会话", mode="markers")
    figure.update_layout(
        title="8 次搜索会话：模拟、精确值与实际分布",
        xaxis_title="每会话橙品数",
        yaxis_title="概率",
        yaxis_tickformat=".2%",
    )
    return figure
