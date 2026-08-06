"""Skill-level comparison and confidence interval charts."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from charts.plotly_chart import bar
from config.settings import MATERIALS, SKILL_LEVELS
from services.statistics import sample_sufficiency
from ui import configure_page, load_logs, page_guard, show_chart


def render() -> None:
    st.title("技能等级分析")
    selected = st.selectbox("材料范围", ("全部材料", *MATERIALS))
    data = load_logs()
    if selected != "全部材料" and not data.empty:
        data = data[data["material"] == selected]
    if data.empty:
        st.info("当前筛选条件下暂无数据。")
        return
    grouped = data.groupby("skill_level")[["quantity", "red_quantity"]].sum()
    rows = []
    for skill in SKILL_LEVELS:
        total = int(grouped.loc[skill, "quantity"]) if skill in grouped.index else 0
        red = int(grouped.loc[skill, "red_quantity"]) if skill in grouped.index else 0
        info = sample_sufficiency(red, total)
        rows.append({"技能": skill, "产量": total, "红色": red, "掉率": info.rate, "下限": info.ci_low, "上限": info.ci_high, "质量": f"{info.grade} · {info.label}"})
    summary = pd.DataFrame(rows)
    display = summary.copy()
    display["掉率"] = display["掉率"].map(lambda value: f"{value:.2%}")
    display["95% CI"] = [f"{low:.2%} – {high:.2%}" for low, high in zip(summary["下限"], summary["上限"])]
    st.dataframe(display[["技能", "产量", "红色", "掉率", "95% CI", "质量"]], hide_index=True, width="stretch")
    error_figure = go.Figure(go.Scatter(
        x=summary["技能"], y=summary["掉率"], mode="markers+lines",
        error_y={"type": "data", "symmetric": False, "array": summary["上限"] - summary["掉率"], "arrayminus": summary["掉率"] - summary["下限"]},
    ))
    error_figure.update_layout(title="各技能掉率与 95% 置信区间", xaxis_title="技能等级", yaxis_title="掉率")
    left, right = st.columns(2)
    with left:
        show_chart(bar(summary, "技能", "掉率", "各技能掉率"), "skill-rate")
        show_chart(bar(summary, "技能", "产量", "各技能样本量"), "skill-size")
    with right:
        show_chart(error_figure, "skill-error")


configure_page("技能分析", "📊")
page_guard(render)
