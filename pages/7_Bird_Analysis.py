"""Bird quality and species analysis using SQL-level aggregation."""

import pandas as pd
import streamlit as st

from charts.statistical_charts import observed_vs_target_chart, quality_distribution_chart, rate_with_ci_chart
from config.domain import BIRD_RANDOM, BIRD_SPECIES
from services.analysis import comparison_table, proportion_table, quality_distribution, session_summary, species_distribution
from services.statistics import (
    apply_holm_correction, calculate_binomial_test, calculate_chi_square_gof,
    calculate_probability_difference, calculate_proportion, calculate_session_probability, calculate_two_proportion_test,
    classify_sample_quality, interpret_p_value,
)
from ui import configure_page, get_displayed_probabilities, load_quality_analysis, page_guard, show_chart


def _pairwise_species(frame: pd.DataFrame):
    measured = frame[frame["attempts"] > 0].to_dict("records")
    comparisons = []
    for index, first in enumerate(measured):
        for second in measured[index + 1:]:
            comparisons.append(calculate_two_proportion_test(
                int(first["orange"]), int(first["attempts"]), int(second["orange"]), int(second["attempts"]),
                label_a=str(first["item"]), label_b=str(second["item"]),
            ))
    return apply_holm_correction(comparisons)


def render() -> None:
    st.title("灵禽院统计分析")
    st.caption("种类是搜索结果；四种各 25% 仅作为清楚标注的非官方检验假设。")
    level_choice = st.selectbox("等级", (10, "全部等级"))
    level = None if level_choice == "全部等级" else int(level_choice)
    summary, raw_species, sessions = load_quality_analysis(BIRD_RANDOM, None, level)
    targets = get_displayed_probabilities(BIRD_RANDOM)
    total = int(summary.iloc[0]["attempts"]) if not summary.empty else 0
    orange = int(summary.iloc[0]["orange"]) if not summary.empty else 0
    result = calculate_proportion(orange, total)
    cols = st.columns(5)
    cols[0].metric("总搜索数", total)
    cols[1].metric("橙品数", orange)
    cols[2].metric("观测橙品率", "No Data" if result.observed_rate is None else f"{result.observed_rate:.3%}")
    cols[3].metric("95% Wilson CI", "No Data" if result.ci_low is None else f"{result.ci_low:.3%}–{result.ci_high:.3%}")
    cols[4].metric("样本质量", classify_sample_quality(result))
    if not total:
        st.info("当前筛选条件下暂无有效灵禽院数据。No Data 不等于 0%。")
        return
    orange_test = calculate_binomial_test(orange, total, targets["ORANGE"])
    difference = calculate_probability_difference(result.observed_rate, targets["ORANGE"])
    st.caption(f"显示橙品率 1%；概率单位差异 Δ={difference.absolute_difference:+.6f}（{difference.percentage_point_difference:+.3f} pp）；精确二项检验 p={orange_test.p_value:.4g}。{interpret_p_value(orange_test.p_value, '观测橙品率等于显示值 1%')}")

    qualities = quality_distribution(summary, targets)
    qualities = qualities[qualities["quality_key"].isin(("blue", "purple", "orange"))]
    st.subheader("品质分布（79% / 20% / 1%）")
    shown = qualities.copy()
    for column in ("rate", "ci_low", "ci_high", "target"):
        shown[column] = shown[column].map(lambda value: "—" if pd.isna(value) else f"{value:.2%}")
    st.dataframe(shown[["quality", "count", "trials", "rate", "ci_low", "ci_high", "target"]], hide_index=True, width="stretch")
    left, right = st.columns(2)
    with left:
        show_chart(quality_distribution_chart(qualities, "灵禽院品质观测分布"), "bird-quality")
    with right:
        show_chart(observed_vs_target_chart(qualities, "灵禽院品质观测值 vs 显示值"), "bird-quality-target")
    try:
        quality_gof = calculate_chi_square_gof(qualities["count"].tolist(), [0.79, 0.20, 0.01])
        st.caption(f"品质拟合优度检验：χ²={quality_gof.statistic:.3f}，df={quality_gof.degrees_of_freedom}，p={quality_gof.p_value:.4g}。{interpret_p_value(quality_gof.p_value, '观测品质分布符合 79% / 20% / 1% 显示值')}")
    except ValueError as exc:
        st.caption(f"品质拟合优度检验暂不可用：{exc}")

    st.subheader("种类分布：非官方等概率假设")
    species = species_distribution(raw_species, BIRD_SPECIES)
    st.dataframe(species[["item", "attempts", "observed_rate", "expected_count", "count_difference", "residual"]], hide_index=True, width="stretch")
    species_chart = species.rename(columns={"observed_rate": "rate", "item": "species"})
    show_chart(rate_with_ci_chart(species_chart, "species", "灵禽种类观测占比（25% 非官方假设）"), "bird-species")
    try:
        species_gof = calculate_chi_square_gof(species["attempts"].tolist(), [0.25] * 4)
        st.info(f"H0：四种各 25%（非官方）。χ²={species_gof.statistic:.3f}，df={species_gof.degrees_of_freedom}，p={species_gof.p_value:.4g}。{interpret_p_value(species_gof.p_value, '四种灵禽各占 25% 的非官方假设')}")
    except ValueError as exc:
        st.warning(f"非官方 25% 假设检验暂不可用：{exc}")

    st.subheader("各种类橙品率")
    species_rates = proportion_table(species, "item")
    st.dataframe(species_rates, hide_index=True, width="stretch")
    show_chart(rate_with_ci_chart(species_rates, "item", "各灵禽种类橙品率与 95% Wilson CI"), "bird-species-orange")
    comparisons = comparison_table(_pairwise_species(species))
    if comparisons.empty:
        st.caption("至少两个种类有样本后才进行种类橙品率比较。")
    else:
        st.dataframe(comparisons, hide_index=True, width="stretch")
        low_sample_species = species.loc[species["attempts"] < 30, "item"].tolist()
        if low_sample_species:
            st.warning(
                "以下种类样本量低于 30，比较检验能力有限："
                + "、".join(low_sample_species)
            )
        methods = "、".join(sorted(set(comparisons["test"])))
        st.caption(f"实际使用的检验：{methods}；同一比较族统一使用 Holm 校正。")

    st.subheader("会话与 8 次搜索")
    actual = session_summary(sessions)
    exact = calculate_session_probability(targets["ORANGE"], 8)
    session_cols = st.columns(5)
    session_cols[0].metric("会话数", actual["sessions"])
    session_cols[1].metric("平均搜索/会话", "No Data" if actual["average_searches"] is None else f"{actual['average_searches']:.2f}")
    session_cols[2].metric("0 橙会话", actual["zero_orange"])
    session_cols[3].metric(">=1 橙会话", actual["one_or_more"])
    session_cols[4].metric(">=2 橙会话", actual["two_or_more"])
    st.caption(f"若每次独立且 p=1%，8 次搜索精确概率：0 橙 {exact.zero:.3%}，恰好 1 橙 {exact.exactly_one:.3%}，≥1 橙 {exact.at_least_one:.3%}，≥2 橙 {exact.at_least_two:.3%}。此处未使用 Monte Carlo。")


configure_page("灵禽院分析", "🦅")
page_guard(render)
