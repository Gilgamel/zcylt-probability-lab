"""Unified dashboard for material, horse, and bird observations."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from charts.plotly_chart import bar, line
from config.domain import BIRD_RANDOM, HORSE_SEARCH, MATERIAL_PRODUCTION
from ui import get_displayed_probabilities, load_observations, show_chart


def _category_card(
    title: str,
    frame: pd.DataFrame,
    attempt_label: str,
    displayed: float | None = None,
) -> None:
    """Render compact totals for one category."""
    attempts = int(frame["attempt_count"].sum()) if not frame.empty else 0
    orange = int(frame["orange_count"].sum()) if not frame.empty else 0
    rate = orange / attempts if attempts else 0.0
    st.subheader(title)
    columns = st.columns(4 if displayed is not None else 3)
    columns[0].metric(attempt_label, attempts)
    columns[1].metric("红/橙数量", orange)
    columns[2].metric("观测概率", f"{rate:.2%}")
    if displayed is not None:
        columns[3].metric("显示概率", f"{displayed:.2%}")


def render_dashboard() -> None:
    """Render top-level metrics and cross-system collection trends."""
    st.title("ProbabilityLab")
    st.caption("这城有良田 · 统一概率研究平台")
    frame = load_observations()
    if frame.empty:
        st.info("还没有观测记录。请前往“数据录入”选择对应系统添加数据。")
        return
    material = frame[frame["category_type"] == MATERIAL_PRODUCTION]
    horse = frame[frame["category_type"] == HORSE_SEARCH]
    bird = frame[frame["category_type"] == BIRD_RANDOM]
    _category_card("官匠营", material, "总生产量")
    st.divider()
    horse_displayed = get_displayed_probabilities(HORSE_SEARCH).get("ORANGE")
    bird_displayed = get_displayed_probabilities(BIRD_RANDOM).get("ORANGE")
    _category_card("马厩", horse, "总搜索数", horse_displayed)
    st.divider()
    _category_card("灵禽院", bird, "总搜索数", bird_displayed)

    now = datetime.now()
    recent_columns = st.columns(3)
    today_count = int(
        frame[frame["observed_at"].dt.date == now.date()]["attempt_count"].sum()
    )
    week_count = int(
        frame[
            frame["observed_at"].dt.date >= (now - timedelta(days=7)).date()
        ]["attempt_count"].sum()
    )
    month_count = int(
        frame[
            frame["observed_at"].dt.date >= (now - timedelta(days=30)).date()
        ]["attempt_count"].sum()
    )
    recent_columns[0].metric("今日尝试", today_count)
    recent_columns[1].metric("近 7 天尝试", week_count)
    recent_columns[2].metric("近 30 天尝试", month_count)

    daily = frame.assign(date=frame["observed_at"].dt.date).groupby(
        ["date", "category"], as_index=False
    )[["attempt_count", "orange_count"]].sum()
    daily["observed_probability"] = daily["orange_count"] / daily["attempt_count"]
    daily["sample_growth"] = daily.groupby("category")["attempt_count"].cumsum()
    left, right = st.columns(2)
    with left:
        show_chart(bar(daily, "date", "attempt_count", "每日采集量", "category"), "daily")
        show_chart(line(daily, "date", "sample_growth", "累计样本增长", "category"), "growth")
    with right:
        show_chart(line(daily, "date", "observed_probability", "红/橙观测概率趋势", "category"), "trend")
