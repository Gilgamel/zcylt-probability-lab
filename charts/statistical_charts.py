"""Plotly factories for Phase 3 statistical views."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from charts.plotly_chart import empty_chart


def cumulative_rate_chart(frame: pd.DataFrame, title: str = "累计橙品率") -> go.Figure:
    if frame.empty:
        return empty_chart()
    figure = go.Figure(go.Scatter(x=frame["date"], y=frame["rate"], mode="lines+markers"))
    figure.update_layout(title=title, xaxis_title="日期", yaxis_title="观测率", yaxis_tickformat=".2%")
    return figure


def rate_with_ci_chart(
    frame: pd.DataFrame, group_column: str, title: str = "观测率与 95% Wilson 区间"
) -> go.Figure:
    measured = frame[frame["rate"].notna()] if not frame.empty else frame
    if measured.empty:
        return empty_chart()
    lower = measured["rate"] - measured["ci_low"]
    upper = measured["ci_high"] - measured["rate"]
    figure = go.Figure(go.Bar(
        x=measured[group_column].astype(str), y=measured["rate"],
        error_y={"type": "data", "symmetric": False, "array": upper, "arrayminus": lower},
    ))
    figure.update_layout(title=title, xaxis_title="分组", yaxis_title="观测率", yaxis_tickformat=".2%")
    return figure


def quality_distribution_chart(frame: pd.DataFrame, title: str) -> go.Figure:
    measured = frame[frame["rate"].notna()] if not frame.empty else frame
    if measured.empty:
        return empty_chart()
    figure = go.Figure(go.Bar(x=measured["quality"], y=measured["rate"], name="观测率"))
    figure.update_layout(title=title, yaxis_title="比例", yaxis_tickformat=".2%")
    return figure


def observed_vs_target_chart(frame: pd.DataFrame, title: str) -> go.Figure:
    measured = frame[frame["rate"].notna()] if not frame.empty else frame
    if measured.empty:
        return empty_chart()
    figure = go.Figure()
    figure.add_bar(x=measured["quality"], y=measured["rate"], name="观测率")
    targeted = measured[measured["target"].notna()]
    if not targeted.empty:
        figure.add_scatter(x=targeted["quality"], y=targeted["target"], name="显示值", mode="markers", marker={"size": 12})
    figure.update_layout(title=title, yaxis_title="比例", yaxis_tickformat=".2%", barmode="group")
    return figure
