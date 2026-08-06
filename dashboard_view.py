"""Dashboard rendering shared by the landing page and navigation page."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from charts.plotly_chart import bar, line
from ui import load_logs, show_chart


def render_dashboard() -> None:
    st.title("ProbabilityLab")
    st.caption("这城有良田 · 掉率数据分析平台")
    frame = load_logs()
    if frame.empty:
        st.info("还没有生产记录。请前往“数据录入”添加第一条数据。")
        return
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    now = datetime.now()
    total = int(frame["quantity"].sum())
    red = int(frame["red_quantity"].sum())
    today = frame[frame["datetime"].dt.date == now.date()]
    week = frame[frame["datetime"] >= now - timedelta(days=7)]
    month = frame[frame["datetime"] >= now - timedelta(days=30)]
    metrics = (
        ("总产量", total), ("红色总数", red), ("总体掉率", f"{red / total:.2%}"),
        ("今日产量", int(today["quantity"].sum())),
        ("近 7 天", int(week["quantity"].sum())),
        ("近 30 天", int(month["quantity"].sum())),
    )
    for column, (label, value) in zip(st.columns(6), metrics):
        column.metric(label, value)

    material = frame.groupby("material", as_index=False)[["quantity", "red_quantity"]].sum()
    material["drop_rate"] = material["red_quantity"] / material["quantity"]
    daily = frame.assign(date=frame["datetime"].dt.date).groupby("date", as_index=False)[
        ["quantity", "red_quantity"]
    ].sum()
    daily["drop_rate"] = daily["red_quantity"] / daily["quantity"]
    daily["sample_growth"] = daily["quantity"].cumsum()
    left, right = st.columns(2)
    with left:
        show_chart(bar(material.sort_values("drop_rate", ascending=False), "material", "drop_rate", "材料掉率排行"), "rank")
        show_chart(bar(daily, "date", "quantity", "每日产量"), "daily")
    with right:
        show_chart(line(daily, "date", "drop_rate", "掉率趋势"), "trend")
        show_chart(line(daily, "date", "sample_growth", "样本增长"), "growth")
