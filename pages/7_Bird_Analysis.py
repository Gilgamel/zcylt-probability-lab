"""Bird quality, species, and quality-by-species analysis."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from config.domain import BIRD_RANDOM, BIRD_SPECIES, QUALITY_LABELS
from services.statistics import (
    binomial_test,
    chi_square_goodness_of_fit,
    sample_sufficiency,
    session_probability_at_least_one,
)
from services.simulator import simulate_mixed_sessions
from ui import (
    configure_page,
    get_displayed_probabilities,
    get_setting,
    load_observations,
    page_guard,
    show_chart,
    sufficiency_settings,
)


def render() -> None:
    """Render all required bird analyses."""
    st.title("灵禽院分析")
    st.caption("种类是搜索结果；25% 仅可作为用户选择的检验假设，不是官方概率。")
    frame = load_observations(BIRD_RANDOM)
    if frame.empty:
        st.info("暂无灵禽院数据。")
        return
    levels = sorted(frame["level"].unique().tolist())
    selected_level = st.selectbox("等级", ("全部等级", *levels))
    data = frame if selected_level == "全部等级" else frame[frame["level"] == selected_level]
    displayed = get_displayed_probabilities(BIRD_RANDOM)
    total = int(data["attempt_count"].sum())
    orange = int(data["orange_count"].sum())
    displayed_orange = displayed["ORANGE"]
    thresholds, target_margin = sufficiency_settings()
    info = sample_sufficiency(
        orange, total, thresholds, target_margin, planning_probability=displayed_orange
    )
    p_value = binomial_test(orange, total, displayed_orange)
    columns = st.columns(6)
    for column, (label, value) in zip(columns, (
        ("总搜索数", total), ("橙品数", orange), ("观测概率", f"{info.rate:.3%}"),
        ("显示概率", f"{displayed_orange:.2%}"),
        ("差异", f"{(info.rate - displayed_orange) * 100:+.3f} pp"),
        ("精确二项 p", f"{p_value:.4g}"),
    )):
        column.metric(label, value)
    st.caption(
        f"95% CI：{info.ci_low:.3%} – {info.ci_high:.3%} · "
        f"绝对宽度 {info.absolute_ci_width:.3%} · 误差 ±{info.margin_of_error:.3%} · "
        f"{info.grade} {info.label} · 还需约 {info.additional_samples:,} 次搜索"
    )

    quality_columns = {"BLUE": "blue_count", "PURPLE": "purple_count", "ORANGE": "orange_count"}
    quality_rows = []
    observed_counts = []
    for quality, probability in displayed.items():
        count = int(data[quality_columns[quality]].sum())
        observed_counts.append(count)
        quality_rows.append({
            "品质": QUALITY_LABELS[quality], "观测数量": count,
            "观测概率": count / total, "显示概率": probability,
        })
    qualities = pd.DataFrame(quality_rows)
    st.subheader("品质分布")
    st.dataframe(
        qualities.assign(
            观测概率=qualities["观测概率"].map(lambda value: f"{value:.2%}"),
            显示概率=qualities["显示概率"].map(lambda value: f"{value:.2%}"),
        ),
        hide_index=True,
        width="stretch",
    )
    try:
        statistic, distribution_p = chi_square_goodness_of_fit(
            observed_counts, list(displayed.values())
        )
        st.caption(f"品质分布卡方拟合检验：χ²={statistic:.3f}，p={distribution_p:.4g}")
    except ValueError as exc:
        st.caption(f"品质分布检验暂不可用：{exc}")

    st.subheader("种类分布")
    species = data.groupby("item", as_index=False)["attempt_count"].sum().set_index("item")
    species = species.reindex(BIRD_SPECIES, fill_value=0).reset_index()
    species.columns = ["种类", "数量"]
    species["占比"] = species["数量"] / species["数量"].sum()
    st.dataframe(
        species.assign(占比=species["占比"].map(lambda value: f"{value:.2%}")),
        hide_index=True,
        width="stretch",
    )
    show_chart(px.bar(species, x="种类", y="占比", title="灵禽种类观测分布"), "bird-species")
    if st.checkbox("检验假设 H0：四种灵禽各为 25%（非官方概率）"):
        try:
            statistic, species_p = chi_square_goodness_of_fit(
                species["数量"].to_numpy(), np.full(4, 0.25)
            )
            st.info(f"等概率假设检验：χ²={statistic:.3f}，p={species_p:.4g}")
        except ValueError as exc:
            st.warning(f"暂不能进行该检验：{exc}")

    st.subheader("品质 × 种类")
    cross = data.groupby("item")[["blue_count", "purple_count", "orange_count"]].sum()
    cross = cross.reindex(BIRD_SPECIES, fill_value=0).rename(columns={
        "blue_count": "蓝品", "purple_count": "紫品", "orange_count": "橙品",
    })
    st.dataframe(cross, width="stretch")
    heatmap = px.imshow(
        cross.to_numpy(), x=cross.columns, y=cross.index,
        text_auto=True, aspect="auto", title="品质 × 灵禽种类热力图",
    )
    show_chart(heatmap, "bird-quality-species")

    st.subheader("会话分析")
    session_data = data.copy()
    session_data["session_group"] = session_data["session_id"].fillna(
        session_data["id"].map(lambda value: f"legacy-{value}")
    )
    sessions = session_data.groupby("session_group", as_index=False).agg(
        searches=("attempt_count", "sum"),
        orange=("orange_count", "sum"),
    )
    session_count = len(sessions)
    zero = int((sessions["orange"] == 0).sum())
    one_plus = int((sessions["orange"] >= 1).sum())
    two_plus = int((sessions["orange"] >= 2).sum())
    metric_columns = st.columns(5)
    for column, (label, value) in zip(metric_columns, (
        ("会话数", session_count),
        ("平均搜索/会话", f"{sessions['searches'].mean():.2f}"),
        ("0 橙会话", zero),
        (">=1 橙会话", one_plus),
        (">=2 橙会话", two_plus),
    )):
        column.metric(label, value)
    expected_one_plus = sum(
        session_probability_at_least_one(displayed_orange, int(size))
        for size in sessions["searches"]
    ) / session_count
    st.caption(
        f"实际至少 1 橙会话比例：{one_plus / session_count:.2%} · "
        f"按各会话搜索数动态计算的显示模型期望：{expected_one_plus:.2%}"
    )
    show_chart(
        px.histogram(sessions, x="orange", title="实际每会话橙品数量", nbins=9),
        "bird-session-hist",
    )
    if st.button("运行会话 Monte Carlo 对比", key="bird-session-mc"):
        with st.spinner("按实际会话规模分布进行模拟…"):
            simulated_sessions = simulate_mixed_sessions(
                displayed_orange,
                sessions["searches"].to_numpy(),
                int(get_setting("default_monte_carlo_iterations", "100000")),
                int(get_setting("default_random_seed", "42")),
            )
        comparison = px.histogram(
            pd.DataFrame({
                "橙品数": np.concatenate([simulated_sessions, sessions["orange"].to_numpy()]),
                "来源": ["Monte Carlo"] * len(simulated_sessions) + ["实际"] * len(sessions),
            }),
            x="橙品数", color="来源", histnorm="probability", barmode="overlay",
            title="实际 vs Monte Carlo 会话橙品分布", opacity=0.7,
        )
        show_chart(comparison, "bird-session-mc-result")


configure_page("灵禽院分析", "🦅")
page_guard(render)
