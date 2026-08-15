"""Horse quality, breed, hypothesis, and session-level analysis."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.domain import (
    HORSE_BREEDS,
    HORSE_PROBABILITY_WARNING,
    HORSE_SEARCH,
    QUALITY_LABELS,
)
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


def _filter_horse_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply breed, level, date, and session-size filters."""
    breed = st.selectbox("马匹", ("全部马匹", *HORSE_BREEDS))
    levels = sorted(frame["level"].unique().tolist()) if not frame.empty else [10]
    level = st.selectbox("等级", ("全部等级", *levels))
    session_size = st.selectbox("会话搜索次数", ("全部", *range(1, 9)))
    date_range = st.date_input("日期范围", value=(date.today().replace(day=1), date.today()))
    data = frame.copy()
    if data.empty:
        return data
    if breed != "全部马匹":
        data = data[data["item"] == breed]
    if level != "全部等级":
        data = data[data["level"] == level]
    if session_size != "全部":
        data = data[data["attempt_count"] == session_size]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        data = data[
            (data["observed_at"].dt.date >= date_range[0])
            & (data["observed_at"].dt.date <= date_range[1])
        ]
    return data


def render() -> None:
    """Render the full V1.1 horse analysis."""
    st.title("马厩分析")
    st.warning(HORSE_PROBABILITY_WARNING)
    frame = load_observations(HORSE_SEARCH)
    data = _filter_horse_data(frame)
    if data.empty:
        st.info("当前筛选条件下暂无马厩数据。")
        return
    displayed = get_displayed_probabilities(HORSE_SEARCH)
    displayed_orange = displayed["ORANGE"]
    total = int(data["attempt_count"].sum())
    orange = int(data["orange_count"].sum())
    thresholds, target_margin = sufficiency_settings()
    info = sample_sufficiency(
        orange, total, thresholds, target_margin, planning_probability=displayed_orange
    )
    p_value = binomial_test(orange, total, displayed_orange)
    difference = info.rate - displayed_orange
    metrics = (
        ("总搜索数", total),
        ("橙品数", orange),
        ("观测橙品概率", f"{info.rate:.3%}"),
        ("显示橙品概率", f"{displayed_orange:.2%}"),
        ("差异", f"{difference:+.3%} ({difference * 100:+.3f} pp)"),
        ("精确二项检验 p", f"{p_value:.4g}"),
    )
    for column, (label, value) in zip(st.columns(6), metrics):
        column.metric(label, value)
    st.caption(
        f"95% CI：{info.ci_low:.3%} – {info.ci_high:.3%} · "
        f"绝对宽度 {info.absolute_ci_width:.3%} · 误差 ±{info.margin_of_error:.3%} · "
        f"{info.grade} {info.label} · 目标误差还需约 {info.additional_samples:,} 次搜索"
    )

    literal = {**displayed, "OTHER": 1 - sum(displayed.values())}
    count_columns = {
        "GREEN": "green_count", "BLUE": "blue_count", "PURPLE": "purple_count",
        "ORANGE": "orange_count", "OTHER": "unaccounted_count",
    }
    quality_rows = []
    observed_counts = []
    for quality, probability in literal.items():
        count = int(data[count_columns[quality]].sum())
        observed_counts.append(count)
        quality_rows.append({
            "品质": QUALITY_LABELS[quality],
            "观测数量": count,
            "观测概率": count / total,
            "原始显示概率": displayed.get(quality),
            "字面模拟概率": probability,
        })
    quality_frame = pd.DataFrame(quality_rows)
    display_table = quality_frame.copy()
    for column in ("观测概率", "原始显示概率", "字面模拟概率"):
        display_table[column] = display_table[column].map(
            lambda value: "—" if pd.isna(value) else f"{value:.2%}"
        )
    st.subheader("完整品质分布（字面显示模式）")
    st.dataframe(display_table, hide_index=True, width="stretch")
    try:
        statistic, distribution_p = chi_square_goodness_of_fit(
            observed_counts, list(literal.values())
        )
        st.caption(f"完整分布卡方拟合检验：χ²={statistic:.3f}，p={distribution_p:.4g}")
    except ValueError as exc:
        st.caption(f"完整分布检验暂不可用：{exc}")

    st.subheader("马匹品种比较")
    breed_rows = []
    for breed in HORSE_BREEDS:
        subset = frame[frame["item"] == breed]
        breed_total = int(subset["attempt_count"].sum())
        breed_orange = int(subset["orange_count"].sum())
        breed_info = sample_sufficiency(
            breed_orange, breed_total, thresholds, target_margin, displayed_orange
        )
        breed_rows.append({
            "马匹": breed, "搜索数": breed_total, "橙品": breed_orange,
            "概率": breed_info.rate, "下限": breed_info.ci_low, "上限": breed_info.ci_high,
        })
    breeds = pd.DataFrame(breed_rows)
    st.dataframe(
        breeds.assign(
            概率=breeds["概率"].map(lambda value: f"{value:.3%}"),
            **{"95% CI": [f"{low:.3%} – {high:.3%}" for low, high in zip(breeds["下限"], breeds["上限"])]},
        )[["马匹", "搜索数", "橙品", "概率", "95% CI"]],
        hide_index=True,
        width="stretch",
    )
    figure = go.Figure(go.Scatter(
        x=breeds["马匹"], y=breeds["概率"], mode="markers",
        error_y={
            "type": "data", "symmetric": False,
            "array": breeds["上限"] - breeds["概率"],
            "arrayminus": breeds["概率"] - breeds["下限"],
        },
    ))
    figure.add_hline(y=displayed_orange, line_dash="dash", annotation_text="显示概率")
    figure.update_layout(title="品种橙品概率（不预设各品种相同）", yaxis_title="概率")
    show_chart(figure, "horse-breeds")

    st.subheader("会话分析")
    sessions = len(data)
    zero = int((data["orange_count"] == 0).sum())
    one_plus = int((data["orange_count"] >= 1).sum())
    two_plus = int((data["orange_count"] >= 2).sum())
    average_size = total / sessions
    session_columns = st.columns(5)
    for column, (label, value) in zip(session_columns, (
        ("会话数", sessions), ("平均搜索/会话", f"{average_size:.2f}"),
        ("0 橙会话", zero), (">=1 橙会话", one_plus), (">=2 橙会话", two_plus),
    )):
        column.metric(label, value)
    expected_at_least_one = sum(
        session_probability_at_least_one(displayed_orange, int(size))
        for size in data["attempt_count"]
    ) / sessions
    st.caption(
        f"实际至少 1 橙会话比例：{one_plus / sessions:.2%} · "
        f"按每个会话实际搜索数动态计算的显示模型期望：{expected_at_least_one:.2%}"
    )
    show_chart(
        px.histogram(data, x="orange_count", title="实际每会话橙品数量", nbins=9),
        "horse-session-hist",
    )
    if st.button("运行会话 Monte Carlo 对比", key="horse-session-mc"):
        with st.spinner("按实际会话规模分布进行模拟…"):
            simulated_sessions = simulate_mixed_sessions(
                displayed_orange,
                data["attempt_count"].to_numpy(),
                int(get_setting("default_monte_carlo_iterations", "100000")),
                int(get_setting("default_random_seed", "42")),
            )
        comparison = go.Figure()
        comparison.add_histogram(
            x=simulated_sessions, name="Monte Carlo", histnorm="probability", opacity=0.7
        )
        comparison.add_histogram(
            x=data["orange_count"], name="实际", histnorm="probability", opacity=0.6
        )
        comparison.update_layout(
            barmode="overlay", title="实际 vs Monte Carlo 会话橙品分布",
            xaxis_title="每会话橙品数", yaxis_title="比例",
        )
        show_chart(comparison, "horse-session-mc-result")


configure_page("马厩分析", "🐎")
page_guard(render)
