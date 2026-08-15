"""Unified Monte Carlo simulation, real comparison, and probability fitting."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.domain import (
    BIRD_RANDOM,
    BIRD_SPECIES,
    CATEGORIES,
    HORSE_BREEDS,
    HORSE_PROBABILITY_WARNING,
    HORSE_SEARCH,
    MATERIAL_PRODUCTION,
    MATERIALS,
)
from database.db import session_scope
from database.repository import SimulationRepository
from services.estimator import fit_binary_probability
from services.simulator import (
    CategoricalSimulator,
    ProductionSimulator,
    literal_horse_probabilities,
    normalized_probabilities,
    simulation_interval,
)
from services.statistics import confidence_interval
from ui import (
    configure_page,
    get_displayed_probabilities,
    get_setting,
    load_observations,
    page_guard,
    show_chart,
)


def _real_session_orange(
    data: pd.DataFrame,
    searches: int,
    category_type: str,
) -> np.ndarray:
    """Return comparable real orange counts for equal-size sessions."""
    if data.empty:
        return np.array([], dtype=int)
    if category_type == BIRD_RANDOM:
        grouped = data.copy()
        grouped["session_group"] = grouped["session_id"].fillna(
            grouped["id"].map(lambda value: f"legacy-{value}")
        )
        sessions = grouped.groupby("session_group", as_index=False).agg(
            attempts=("attempt_count", "sum"), orange=("orange_count", "sum")
        )
        return sessions.loc[sessions["attempts"] == searches, "orange"].to_numpy()
    return data.loc[data["attempt_count"] == searches, "orange_count"].to_numpy()


def _comparison(
    simulated: np.ndarray,
    real_data: pd.DataFrame,
    searches: int,
    displayed_probability: float | None,
    simulation_probability: float,
    category_type: str,
) -> None:
    """Show explicit observed/displayed/simulated values and overlay distributions."""
    total = int(real_data["attempt_count"].sum()) if not real_data.empty else 0
    orange = int(real_data["orange_count"].sum()) if not real_data.empty else 0
    observed_probability = orange / total if total else float("nan")
    ci_low, ci_high = confidence_interval(orange, total)
    simulated_rates = simulated / searches
    sim_low, sim_high = simulation_interval(simulated_rates)
    rows = [
        {"概率类型": "观测概率", "值": observed_probability},
        {"概率类型": "显示概率", "值": displayed_probability},
        {"概率类型": "Monte Carlo 模拟概率", "值": float(simulated_rates.mean())},
        {"概率类型": "模拟输入概率", "值": simulation_probability},
    ]
    table = pd.DataFrame(rows)
    table["值"] = table["值"].map(lambda value: "—" if pd.isna(value) else f"{value:.4%}")
    st.subheader("真实 vs Monte Carlo")
    st.dataframe(table, hide_index=True, width="stretch")
    if total:
        difference = observed_probability - simulation_probability
        st.caption(
            f"观测与模拟输入差异：{difference * 100:+.4f} pp · "
            f"观测 95% CI：{ci_low:.4%} – {ci_high:.4%} · "
            f"模拟 95% 区间：{sim_low:.4%} – {sim_high:.4%}"
        )
    else:
        st.caption(f"尚无真实数据 · 模拟 95% 区间：{sim_low:.4%} – {sim_high:.4%}")
    figure = go.Figure()
    figure.add_histogram(x=simulated, name="模拟", opacity=0.70, histnorm="probability")
    real_counts = _real_session_orange(real_data, searches, category_type)
    if real_counts.size:
        figure.add_histogram(x=real_counts, name="真实", opacity=0.60, histnorm="probability")
    figure.update_layout(
        barmode="overlay", title="相同会话规模的橙品数量分布",
        xaxis_title="每会话橙品数", yaxis_title="比例",
    )
    show_chart(figure, "mc-overlay")


def _persist_run(
    category_type: str,
    item: str | None,
    model_name: str,
    probability: float,
    searches: int,
    iterations: int,
    seed: int,
    simulated: np.ndarray,
) -> None:
    """Persist reproducibility metadata and summary, not the full random array."""
    result = {
        "mean": float(simulated.mean()),
        "median": float(np.median(simulated)),
        "std": float(simulated.std()),
        "min": int(simulated.min()),
        "max": int(simulated.max()),
    }
    with session_scope() as session:
        SimulationRepository(session).add(
            category_type, model_name, probability, searches, iterations, seed, result, item
        )


def _simulation_tab() -> None:
    """Render category-specific simulation controls."""
    category_type = st.selectbox(
        "模拟系统",
        tuple(CATEGORIES),
        format_func=lambda value: CATEGORIES[value],
        key="simulation-category",
    )
    default_iterations = int(get_setting("default_monte_carlo_iterations", "100000"))
    default_seed = int(get_setting("default_random_seed", "42"))
    c1, c2, c3 = st.columns(3)
    searches = int(c1.number_input(
        "每会话尝试次数",
        min_value=1,
        max_value=8 if category_type in {HORSE_SEARCH, BIRD_RANDOM} else 10000,
        value=1 if category_type in {HORSE_SEARCH, BIRD_RANDOM} else int(get_setting("default_material_quantity", "18")),
    ))
    iterations = int(c2.number_input("模拟迭代次数", 100, 2_000_000, default_iterations, 1000))
    seed = int(c3.number_input("固定随机种子", 0, 2_147_483_647, default_seed, 1))
    item: str | None = None
    displayed_probability: float | None = None
    model_name = "independent_bernoulli"
    simulation_probability: float
    simulate_equal_species = False

    if category_type == MATERIAL_PRODUCTION:
        item = st.selectbox("材料", MATERIALS)
        simulation_probability = st.number_input(
            "模拟输入概率 (%)（候选值，不是官方显示概率）", 0.0, 100.0, 3.0, 0.01
        ) / 100
        probabilities = None
    elif category_type == HORSE_SEARCH:
        st.warning(HORSE_PROBABILITY_WARNING)
        item = st.selectbox("马匹", HORSE_BREEDS)
        displayed = get_displayed_probabilities(HORSE_SEARCH)
        mode = st.radio(
            "马厩模拟模式",
            ("字面显示模式（明确包含 Other / 未说明余量）", "仅用于模拟的归一化概率"),
        )
        if mode.startswith("字面"):
            probabilities = literal_horse_probabilities(displayed)
            model_name = "horse_literal_multinomial"
        else:
            probabilities = normalized_probabilities(displayed)
            model_name = "horse_normalized_multinomial"
            st.info("仅用于模拟的归一化概率；不会写回或替代官方显示概率。")
        displayed_probability = displayed["ORANGE"]
        simulation_probability = probabilities["ORANGE"]
    else:
        st.caption("主品质模拟不假设四种灵禽等概率；种类假设由灵禽分析页单独检验。")
        displayed = get_displayed_probabilities(BIRD_RANDOM)
        probabilities = displayed
        displayed_probability = displayed["ORANGE"]
        simulation_probability = displayed_probability
        model_name = "bird_quality_multinomial"
        simulate_equal_species = st.checkbox(
            "同时模拟种类分布：明确采用四种各 25% 的检验假设（非官方概率）"
        )

    if st.button("运行并保存模拟", type="primary", width="stretch"):
        with st.spinner("正在进行可复现的向量化 Monte Carlo 模拟…"):
            if category_type == MATERIAL_PRODUCTION:
                simulated = ProductionSimulator(
                    simulation_probability, searches, iterations, seed
                ).simulate()
            else:
                simulator = CategoricalSimulator(probabilities, searches, iterations, seed)
                simulated = simulator.outcome_counts("ORANGE")
        metrics = (
            ("均值", simulated.mean()), ("中位数", np.median(simulated)),
            ("标准差", simulated.std()), ("最小值", simulated.min()), ("最大值", simulated.max()),
        )
        for column, (label, value) in zip(st.columns(5), metrics):
            column.metric(label, f"{value:.4f}")
        zero_probability = float(np.mean(simulated == 0))
        one_probability = float(np.mean(simulated >= 1))
        two_probability = float(np.mean(simulated >= 2))
        st.caption(
            f"期望橙品数：{simulated.mean():.4f} · P(0 橙)={zero_probability:.3%} · "
            f"P(≥1 橙)={one_probability:.3%} · P(≥2 橙)={two_probability:.3%}"
        )
        real_data = load_observations(category_type)
        if item and category_type != BIRD_RANDOM:
            real_data = real_data[real_data["item"] == item]
        _comparison(
            simulated, real_data, searches, displayed_probability,
            simulation_probability, category_type,
        )
        if category_type == BIRD_RANDOM and simulate_equal_species:
            species_probabilities = {species: 0.25 for species in BIRD_SPECIES}
            species_results = CategoricalSimulator(
                species_probabilities, searches, iterations, seed + 1
            ).simulate()
            species_summary = pd.DataFrame({
                "种类": BIRD_SPECIES,
                "每会话模拟均值": species_results.mean(axis=0),
                "检验假设概率": [0.25] * 4,
            })
            st.subheader("灵禽种类模拟（用户明确选择的 25% 检验假设）")
            st.dataframe(species_summary, hide_index=True, width="stretch")
        _persist_run(
            category_type, item, model_name, simulation_probability,
            searches, iterations, seed, simulated,
        )
        st.success("模拟摘要、模型、概率、迭代次数和随机种子已保存。")


def _fitting_tab() -> None:
    """Fit orange probability for each supported category."""
    category_type = st.selectbox(
        "拟合系统",
        tuple(CATEGORIES),
        format_func=lambda value: CATEGORIES[value],
        key="fit-category",
    )
    data = load_observations(category_type)
    item: str | None = None
    if category_type == MATERIAL_PRODUCTION:
        item = st.selectbox("材料", MATERIALS, key="fit-material")
    elif category_type == HORSE_SEARCH:
        item = st.selectbox("马匹", HORSE_BREEDS, key="fit-horse")
    if item:
        data = data[data["item"] == item]
    displayed = (
        get_displayed_probabilities(category_type).get("ORANGE")
        if category_type != MATERIAL_PRODUCTION else None
    )
    defaults = (0.5, 1.5) if displayed is not None else (0.5, 6.0)
    c1, c2, c3 = st.columns(3)
    minimum = c1.number_input("最小概率 (%)", 0.0, 100.0, defaults[0], 0.01)
    maximum = c2.number_input("最大概率 (%)", 0.0, 100.0, defaults[1], 0.01)
    step = c3.number_input("步长（百分点）", 0.01, 10.0, 0.01, 0.01)
    iterations = int(st.number_input("每个候选迭代次数", 1000, 500_000, 50_000, 1000))
    seed = int(st.number_input("拟合随机种子", 0, 2_147_483_647, int(get_setting("default_random_seed", "42"))))
    if st.button("搜索最佳拟合概率", type="primary"):
        total = int(data["attempt_count"].sum()) if not data.empty else 0
        successes = int(data["orange_count"].sum()) if not data.empty else 0
        with st.spinner("正在模拟并比较所有候选概率…"):
            result = fit_binary_probability(
                successes, total, minimum / 100, maximum / 100, step / 100,
                iterations, seed, displayed,
            )
        best = result.iloc[0]
        observed_mle = successes / total
        columns = st.columns(3)
        columns[0].metric("观测概率 / MLE", f"{observed_mle:.4%}")
        columns[1].metric("Monte Carlo 最佳拟合概率", f"{best['probability']:.4%}")
        if displayed is not None:
            displayed_rows = result[result["is_displayed_probability"]]
            rank = int(displayed_rows.iloc[0]["rank"]) if not displayed_rows.empty else None
            columns[2].metric("显示概率排名", rank if rank is not None else "不在候选网格")
        else:
            columns[2].metric("显示概率", "未配置")
        st.caption("独立 Bernoulli 模型下观测成功率是自然最大似然估计；模拟拟合用于验证和模型比较。")
        top = result.head(10).copy()
        for column in ("probability", "simulated_probability", "error_score"):
            top[column] = top[column].map(lambda value: f"{value:.5%}")
        st.dataframe(
            top.rename(columns={
                "rank": "排名", "probability": "候选概率",
                "simulated_probability": "模拟概率", "error_score": "误差分数",
                "is_displayed_probability": "是否显示概率",
            }),
            hide_index=True,
            width="stretch",
        )


def render() -> None:
    """Render simulation and fitting tabs."""
    st.title("Monte Carlo 与参数拟合")
    simulate_tab, fitting_tab = st.tabs(["统一模拟", "橙品概率拟合"])
    with simulate_tab:
        _simulation_tab()
    with fitting_tab:
        _fitting_tab()


configure_page("Monte Carlo", "🎲")
page_guard(render)
