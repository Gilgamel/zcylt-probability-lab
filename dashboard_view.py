"""Unified dashboard for material, horse, and bird observations."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from charts.plotly_chart import bar, line
from config.domain import BIRD_RANDOM, HORSE_SEARCH, MATERIAL_PRODUCTION
from ui import (
    get_displayed_probabilities,
    load_dashboard_data,
    show_chart,
    show_database_status,
)


def _category_card(
    title: str,
    attempts: int,
    orange: int,
    attempt_label: str,
    displayed: float | None = None,
) -> None:
    """Render compact totals for one category."""
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
    show_database_status()
    totals, daily = load_dashboard_data()
    if totals.empty or int(totals["records"].sum()) == 0:
        st.info("还没有观测记录。请前往“数据录入”选择对应系统添加数据。")
        return
    category_totals = totals.set_index("category_type")

    def values(category_type: str) -> tuple[int, int]:
        if category_type not in category_totals.index:
            return 0, 0
        row = category_totals.loc[category_type]
        return int(row["attempts"]), int(row["orange"])

    material_attempts, material_orange = values(MATERIAL_PRODUCTION)
    horse_attempts, horse_orange = values(HORSE_SEARCH)
    bird_attempts, bird_orange = values(BIRD_RANDOM)
    _category_card("官匠营", material_attempts, material_orange, "总生产量")
    st.divider()
    horse_displayed = get_displayed_probabilities(HORSE_SEARCH).get("ORANGE")
    bird_displayed = get_displayed_probabilities(BIRD_RANDOM).get("ORANGE")
    _category_card("马厩", horse_attempts, horse_orange, "总搜索数", horse_displayed)
    st.divider()
    _category_card("灵禽院", bird_attempts, bird_orange, "总搜索数", bird_displayed)

    now = datetime.now()
    recent_columns = st.columns(3)
    today_count = int(
        daily[daily["date"].dt.date == now.date()]["attempt_count"].sum()
    )
    week_count = int(
        daily[
            daily["date"].dt.date >= (now - timedelta(days=7)).date()
        ]["attempt_count"].sum()
    )
    month_count = int(
        daily[
            daily["date"].dt.date >= (now - timedelta(days=30)).date()
        ]["attempt_count"].sum()
    )
    recent_columns[0].metric("今日尝试", today_count)
    recent_columns[1].metric("近 7 天尝试", week_count)
    recent_columns[2].metric("近 30 天尝试", month_count)

    daily["observed_probability"] = daily["orange_count"] / daily["attempt_count"]
    daily["sample_growth"] = daily.groupby("category")["attempt_count"].cumsum()
    left, right = st.columns(2)
    with left:
        show_chart(bar(daily, "date", "attempt_count", "每日采集量", "category"), "daily")
        show_chart(line(daily, "date", "sample_growth", "累计样本增长", "category"), "growth")
    with right:
        show_chart(line(daily, "date", "observed_probability", "红/橙观测概率趋势", "category"), "trend")
