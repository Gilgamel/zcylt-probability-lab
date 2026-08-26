"""Unified dashboard for material, horse, and bird observations."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from charts.plotly_chart import bar, line
from config.domain import BIRD_RANDOM, BIRD_TARGETED, HORSE_SEARCH, MATERIAL_PRODUCTION
from services.analysis import dashboard_daily_metrics
from services.statistics import calculate_proportion, classify_sample_quality
from ui import (
    get_displayed_probabilities,
    load_dashboard_data,
    show_chart,
    show_database_status,
)


def _category_card(
    title: str,
    records: int,
    attempts: int,
    orange: int,
    attempt_label: str,
    success_label: str,
    items_with_data: int | None = None,
    displayed: float | None = None,
) -> None:
    """Render compact totals for one category."""
    result = calculate_proportion(orange, attempts)
    st.subheader(title)
    metric_count = 4 + int(items_with_data is not None) + int(displayed is not None)
    columns = st.columns(metric_count)
    empty_value: int | str = "No Data" if records == 0 else records
    columns[0].metric("观测记录", empty_value)
    offset = 1
    if items_with_data is not None:
        columns[offset].metric("有数据材料", "No Data" if records == 0 else items_with_data)
        offset += 1
    columns[offset].metric(attempt_label, "No Data" if records == 0 else attempts)
    columns[offset + 1].metric(success_label, "No Data" if records == 0 else orange)
    columns[offset + 2].metric(
        "观测概率",
        "No Data" if result.observed_rate is None else f"{result.observed_rate:.2%}",
        help=(
            "尚未测量" if result.ci_low is None
            else f"95% Wilson CI {result.ci_low:.2%}–{result.ci_high:.2%} · {classify_sample_quality(result)}"
        ),
    )
    if displayed is not None:
        columns[offset + 3].metric("显示概率", f"{displayed:.2%}")


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

    def values(category_type: str) -> tuple[int, int, int, int]:
        if category_type not in category_totals.index:
            return 0, 0, 0, 0
        row = category_totals.loc[category_type]
        return int(row["records"]), int(row["items_with_data"]), int(row["attempts"]), int(row["orange"])

    material_records, material_items, material_attempts, material_orange = values(MATERIAL_PRODUCTION)
    horse_records, _, horse_attempts, horse_orange = values(HORSE_SEARCH)
    bird_records, _, bird_attempts, bird_orange = values(BIRD_RANDOM)
    targeted_records, _, targeted_attempts, targeted_orange = values(BIRD_TARGETED)
    bird_records += targeted_records
    bird_attempts += targeted_attempts
    bird_orange += targeted_orange
    _category_card("官匠营", material_records, material_attempts, material_orange, "总生产量", "红色数量", material_items)
    st.divider()
    horse_displayed = get_displayed_probabilities(HORSE_SEARCH).get("ORANGE")
    bird_displayed = (
        get_displayed_probabilities(BIRD_RANDOM).get("ORANGE")
        if targeted_records == 0
        else None
    )
    _category_card("马厩", horse_records, horse_attempts, horse_orange, "总搜索数", "橙品数量", displayed=horse_displayed)
    st.divider()
    _category_card("灵禽院", bird_records, bird_attempts, bird_orange, "总培养数", "橙品数量", displayed=bird_displayed)

    today = datetime.now().date()
    observed_dates = daily["date"].dt.date
    recent_columns = st.columns(3)
    today_count = int(
        daily[observed_dates == today]["attempt_count"].sum()
    )
    week_count = int(
        daily[
            (observed_dates >= today - timedelta(days=6))
            & (observed_dates <= today)
        ]["attempt_count"].sum()
    )
    month_count = int(
        daily[
            (observed_dates >= today - timedelta(days=29))
            & (observed_dates <= today)
        ]["attempt_count"].sum()
    )
    metric_help = (
        "所有分类的实际样本次数合计，不是数据库记录条数。"
        "官匠营按生产数量、马厩按搜索次数、灵禽院按培养次数计算。"
    )
    recent_columns[0].metric("今日样本次数", today_count, help=metric_help)
    recent_columns[1].metric("近 7 日样本次数", week_count, help=metric_help)
    recent_columns[2].metric("近 30 日样本次数", month_count, help=metric_help)
    st.caption(
        "以上均为全部分类的实际尝试次数；近 7 日和近 30 日均包含今天，"
        "三个时间范围相互包含，不是新增量，也不是观测记录条数。"
    )

    daily = dashboard_daily_metrics(daily)
    left, right = st.columns(2)
    with left:
        show_chart(bar(daily, "date", "attempt_count", "每日采集量", "category"), "daily")
        show_chart(
            line(daily, "date", "sample_growth", "各分类累计尝试次数", "category"),
            "growth",
        )
        st.caption("每条线分别累计该分类的实际尝试次数；无新增数据的日期保持不变。")
    with right:
        show_chart(line(daily, "date", "observed_probability", "目标品质观测概率趋势", "category"), "trend")
