"""Horse analysis using exact tests and SQL-level aggregation."""

import pandas as pd
import streamlit as st

from charts.statistical_charts import observed_vs_target_chart, quality_distribution_chart, rate_with_ci_chart
from config.domain import HORSE_BREEDS, HORSE_PROBABILITY_WARNING, HORSE_SEARCH
from services.analysis import comparison_table, proportion_table, quality_distribution, session_summary
from services.statistics import (
    apply_holm_correction, calculate_binomial_test, calculate_chi_square_gof,
    calculate_probability_difference, calculate_proportion, calculate_session_probability, calculate_two_proportion_test,
    classify_sample_quality, interpret_p_value,
)
from ui import configure_page, get_displayed_probabilities, load_quality_analysis, page_guard, show_chart


def _all_pairwise(frame: pd.DataFrame):
    records = frame.to_dict("records")
    comparisons = []
    for index, first in enumerate(records):
        for second in records[index + 1:]:
            if int(first["attempts"]) and int(second["attempts"]):
                comparisons.append(calculate_two_proportion_test(
                    int(first["orange"]), int(first["attempts"]), int(second["orange"]), int(second["attempts"]),
                    label_a=str(first["item"]), label_b=str(second["item"]),
                ))
    return apply_holm_correction(comparisons)


def render() -> None:
    st.title("马厩统计分析")
    st.warning(HORSE_PROBABILITY_WARNING)
    left, right = st.columns(2)
    breed_choice = left.selectbox("马匹", ("全部马匹", *HORSE_BREEDS))
    level_choice = right.selectbox("等级", (10, "全部等级"))
    breed = None if breed_choice == "全部马匹" else breed_choice
    level = None if level_choice == "全部等级" else int(level_choice)
    summary, by_breed, sessions = load_quality_analysis(HORSE_SEARCH, breed, level)
    targets = get_displayed_probabilities(HORSE_SEARCH)
    total = int(summary.iloc[0]["attempts"]) if not summary.empty else 0
    orange = int(summary.iloc[0]["orange"]) if not summary.empty else 0
    result = calculate_proportion(orange, total)
    metrics = st.columns(5)
    metrics[0].metric("总搜索数", total)
    metrics[1].metric("橙品数", orange)
    metrics[2].metric("观测橙品率", "No Data" if result.observed_rate is None else f"{result.observed_rate:.3%}")
    metrics[3].metric("95% Wilson CI", "No Data" if result.ci_low is None else f"{result.ci_low:.3%}–{result.ci_high:.3%}")
    metrics[4].metric("样本质量", classify_sample_quality(result))
    if not total:
        st.info("当前筛选条件下暂无有效马厩数据。No Data 不等于 0%。")
        return
    orange_test = calculate_binomial_test(orange, total, targets["ORANGE"])
    difference = calculate_probability_difference(result.observed_rate, targets["ORANGE"])
    st.caption(f"显示橙品率 1%；概率单位差异 Δ={difference.absolute_difference:+.6f}（{difference.percentage_point_difference:+.3f} pp）；精确二项检验 p={orange_test.p_value:.4g}。{interpret_p_value(orange_test.p_value, '观测橙品率等于显示值 1%')} ")

    literal_targets = {**targets, "OTHER": 0.01}
    qualities = quality_distribution(summary, literal_targets)
    st.subheader("五类品质分布")
    shown = qualities.copy()
    for column in ("rate", "ci_low", "ci_high", "target"):
        shown[column] = shown[column].map(lambda value: "—" if pd.isna(value) else f"{value:.2%}")
    st.dataframe(shown[["quality", "count", "trials", "rate", "ci_low", "ci_high", "target"]], hide_index=True, width="stretch")
    chart_left, chart_right = st.columns(2)
    with chart_left:
        show_chart(quality_distribution_chart(qualities, "马厩品质观测分布"), "horse-quality")
    with chart_right:
        show_chart(observed_vs_target_chart(qualities, "马厩观测值 vs 字面显示值"), "horse-target")
    st.caption("第五类 1% 是为解释显示值合计 99% 而保留的“其他 / 未说明”概念，不是官方公布品质概率。")
    try:
        gof = calculate_chi_square_gof(qualities["count"].tolist(), [0.41, 0.50, 0.07, 0.01, 0.01])
        st.write(f"五类 Pearson 拟合优度检验：χ²={gof.statistic:.3f}，df={gof.degrees_of_freedom}，p={gof.p_value:.4g}。{interpret_p_value(gof.p_value, '观测分布符合含未说明类别的字面模型')}")
    except ValueError as exc:
        st.caption(f"五类拟合优度检验暂不可用：{exc}")

    st.subheader("品种橙品率")
    breed_rates = proportion_table(by_breed, "item")
    st.dataframe(breed_rates, hide_index=True, width="stretch")
    show_chart(rate_with_ci_chart(breed_rates, "item", "马匹品种橙品率与 95% Wilson CI"), "horse-breeds")
    breed_comparisons = comparison_table(_all_pairwise(by_breed))
    if not breed_comparisons.empty:
        st.dataframe(breed_comparisons, hide_index=True, width="stretch")
        st.caption("品种比较已用 Holm 方法控制多重检验；小样本采用 Fisher 精确检验。")

    st.subheader("会话与 8 次搜索")
    actual = session_summary(sessions)
    exact = calculate_session_probability(targets["ORANGE"], 8)
    cols = st.columns(5)
    cols[0].metric("会话数", actual["sessions"])
    cols[1].metric("平均搜索/会话", "No Data" if actual["average_searches"] is None else f"{actual['average_searches']:.2f}")
    cols[2].metric("0 橙会话", actual["zero_orange"])
    cols[3].metric(">=1 橙会话", actual["one_or_more"])
    cols[4].metric(">=2 橙会话", actual["two_or_more"])
    st.caption(f"若每次独立且 p=1%，8 次搜索的精确二项概率：0 橙 {exact.zero:.3%}，恰好 1 橙 {exact.exactly_one:.3%}，≥1 橙 {exact.at_least_one:.3%}，≥2 橙 {exact.at_least_two:.3%}。此处未使用 Monte Carlo。")


configure_page("马厩分析", "🐎")
page_guard(render)
