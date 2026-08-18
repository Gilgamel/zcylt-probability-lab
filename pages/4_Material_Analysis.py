"""Material and skill-level statistical analysis using SQL aggregates."""

import pandas as pd
import streamlit as st

from charts.statistical_charts import cumulative_rate_chart, rate_with_ci_chart
from config.domain import MATERIALS, SKILL_LEVELS
from services.analysis import (
    aggregate_proportion, comparison_table, complete_level_table,
    cumulative_daily, pairwise_level_comparisons,
)
from services.statistics import calculate_margin_of_error, calculate_sample_size, classify_sample_quality
from ui import configure_page, load_material_analysis, page_guard, show_chart


def _format_rate(value: float | None) -> str:
    return "No Data" if value is None or pd.isna(value) else f"{value:.3%}"


def render() -> None:
    st.title("官匠营统计分析")
    st.caption("所有概率均为原始观测率；未配置官方目标概率（Official target probability not configured）。")
    left, right = st.columns(2)
    material_choice = left.selectbox("材料", ("全部材料", *MATERIALS))
    level_choice = right.selectbox("技能等级", ("全部等级", *SKILL_LEVELS))
    material = None if material_choice == "全部材料" else material_choice
    level = None if level_choice == "全部等级" else int(level_choice)
    grouped, daily = load_material_analysis(material, level)
    overall = aggregate_proportion(grouped)
    if overall.trials == 0:
        st.info("当前筛选条件下暂无有效数据。No Data 表示尚未测量，不等于 0%。")
    metrics = st.columns(5)
    metrics[0].metric("总生产量", overall.trials)
    metrics[1].metric("红色数量", overall.successes)
    metrics[2].metric("观测红色率", _format_rate(overall.observed_rate))
    metrics[3].metric("95% Wilson CI", "No Data" if overall.ci_low is None else f"{overall.ci_low:.3%}–{overall.ci_high:.3%}")
    metrics[4].metric("样本质量", classify_sample_quality(overall))

    if overall.trials:
        with st.expander("样本量规划", expanded=False):
            planning_probability = st.number_input("规划概率", min_value=0.001, max_value=0.999, value=float(overall.observed_rate or 0.01), step=0.001, format="%.3f")
            confidence = st.selectbox("置信水平", (0.90, 0.95, 0.99), index=1, format_func=lambda value: f"{value:.0%}")
            margin = st.selectbox("目标误差范围", (0.05, 0.02, 0.01, 0.005), index=2, format_func=lambda value: f"±{value:.1%}")
            plan = calculate_sample_size(planning_probability, margin, confidence, overall.trials)
            current_margin = calculate_margin_of_error(overall)
            st.write(f"当前 n={plan.current_samples:,}；当前 Wilson 误差约 ±{current_margin:.2%}；估算所需 n={plan.required_samples:,}；还需约 {plan.remaining_samples:,}。")
            st.caption("这是基于指定概率与正态近似的规划估算，不保证最终 Wilson 区间达到目标宽度。")

    cumulative = cumulative_daily(daily)
    show_chart(cumulative_rate_chart(cumulative, "官匠营累计红色率"), "material-cumulative")
    if not cumulative.empty:
        daily_display = cumulative[["date", "attempts", "orange", "daily_rate", "rate"]].copy()
        daily_display["daily_rate"] = daily_display["daily_rate"].map(lambda value: f"{value:.3%}")
        daily_display["rate"] = daily_display["rate"].map(lambda value: f"{value:.3%}")
        st.dataframe(daily_display.rename(columns={"rate": "cumulative_rate"}), hide_index=True, width="stretch")

    st.subheader("技能等级 9–12")
    levels = complete_level_table(grouped)
    display = levels.copy()
    display["rate"] = display["rate"].map(_format_rate)
    display["95% Wilson CI"] = ["No Data" if pd.isna(low) else f"{low:.3%}–{high:.3%}" for low, high in zip(levels["ci_low"], levels["ci_high"])]
    st.dataframe(display[["level", "trials", "successes", "rate", "95% Wilson CI", "sample_quality"]], hide_index=True, width="stretch")
    show_chart(rate_with_ci_chart(levels, "level", "技能等级红色率与 95% Wilson CI"), "material-level-ci")

    comparisons = comparison_table(pairwise_level_comparisons(grouped))
    st.subheader("预设等级比较（Holm 多重校正）")
    if comparisons.empty:
        st.info("至少需要两个相关等级都有数据才能比较。")
    else:
        shown = comparisons.copy()
        for column in ("rate_a", "rate_b"):
            shown[column] = shown[column].map(lambda value: f"{value:.3%}")
        shown["absolute_difference"] = shown["absolute_difference"].map(lambda value: f"{value:+.6f}")
        shown["percentage_point_difference"] = shown["percentage_point_difference"].map(lambda value: f"{value:+.3f} pp")
        st.dataframe(shown, hide_index=True, width="stretch")
        st.caption("α=0.05；significant 使用 Holm 校正后的 p 值。稀疏样本使用 Fisher 精确检验，否则使用两比例 z 检验；结论是关联证据，不证明因果。")


configure_page("官匠营分析")
page_guard(render)
