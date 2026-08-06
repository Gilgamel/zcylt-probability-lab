"""Per-material descriptive and time-series analysis."""

import pandas as pd
import streamlit as st

from charts.plotly_chart import bar, histogram, line
from config.settings import MATERIALS
from services.statistics import sample_sufficiency
from ui import configure_page, load_logs, page_guard, show_chart


def render() -> None:
    st.title("材料分析")
    frame = load_logs()
    material = st.selectbox("选择材料", MATERIALS)
    data = frame[frame["material"] == material].copy() if not frame.empty else frame
    if data.empty:
        st.info("该材料暂无数据。")
        return
    data["datetime"] = pd.to_datetime(data["datetime"])
    total, red = int(data["quantity"].sum()), int(data["red_quantity"].sum())
    info = sample_sufficiency(red, total)
    labels = ("总产量", "红色数量", "掉率", "95% 置信区间", "样本质量")
    values = (total, red, f"{info.rate:.2%}", f"{info.ci_low:.2%} – {info.ci_high:.2%}", f"{info.grade} · {info.label}")
    for column, label, value in zip(st.columns(5), labels, values):
        column.metric(label, value)
    st.caption(f"误差范围（95%）：±{info.margin_of_error:.2%}")

    data["date"] = data["datetime"].dt.floor("D")
    data["week"] = data["datetime"].dt.to_period("W").dt.start_time
    data["month"] = data["datetime"].dt.to_period("M").dt.start_time
    left, right = st.columns(2)
    for container, period, title in (
        (left, "date", "每日掉率"), (right, "week", "每周掉率"), (left, "month", "每月掉率")
    ):
        grouped = data.groupby(period, as_index=False)[["quantity", "red_quantity"]].sum()
        grouped["drop_rate"] = grouped["red_quantity"] / grouped["quantity"]
        with container:
            show_chart(line(grouped, period, "drop_rate", title), f"material-{period}")
    with right:
        show_chart(histogram(data["red_quantity"], "单次红色数量分布"), "material-hist")


configure_page("材料分析", "💎")
page_guard(render)
