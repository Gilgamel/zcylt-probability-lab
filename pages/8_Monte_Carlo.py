"""Phase 4 Monte Carlo simulation and development-safe result history."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from charts.monte_carlo_charts import (
    binary_count_distribution_chart,
    binary_rate_distribution_chart,
    multinomial_comparison_chart,
    session_distribution_chart,
)
from config.domain import (
    BIRD_RANDOM,
    BIRD_SPECIES,
    HORSE_BREEDS,
    HORSE_PROBABILITY_WARNING,
    HORSE_SEARCH,
    MATERIAL_PRODUCTION,
    MATERIALS,
    QUALITY_LABELS,
    SKILL_LEVELS,
)
from services.monte_carlo import (
    BIRD_EQUAL_SPECIES_MODEL,
    BIRD_QUALITY_MODEL,
    DEFAULT_SIMULATIONS,
    HORSE_LITERAL_MODEL,
    MAX_SEED,
    MAX_TRIALS,
    MATERIAL_EMPIRICAL_MODEL,
    MATERIAL_USER_MODEL,
    SIMULATION_OPTIONS,
    BinaryMonteCarloResult,
    MultinomialMonteCarloResult,
    binary_summary_frame,
    multinomial_summary_frame,
    session_probability_frame,
    simulate_binary,
    simulate_multinomial,
)
from services.simulator import literal_horse_probabilities
from services.statistics import (
    calculate_binomial_test,
    calculate_chi_square_gof,
    interpret_p_value,
)
from ui import (
    configure_page,
    get_displayed_probabilities,
    load_material_analysis,
    load_quality_analysis,
    load_simulation_history,
    page_guard,
    save_simulation_run,
    show_chart,
)


MODEL_LABELS = {
    MATERIAL_USER_MODEL: "官匠营：用户指定理论概率（非官方概率）",
    MATERIAL_EMPIRICAL_MODEL: "官匠营：由当前筛选数据得到的经验概率（非官方概率）",
    HORSE_LITERAL_MODEL: "马厩：字面显示 41% / 50% / 7% / 1% + 未说明 1%",
    BIRD_QUALITY_MODEL: "灵禽品质：79% / 20% / 1%",
    BIRD_EQUAL_SPECIES_MODEL: "灵禽种类：各 25% 检验假设（非官方概率）",
}
def _actual_quality_counts(frame: pd.DataFrame, include_green: bool) -> tuple[int, dict[str, int]]:
    if frame.empty or int(frame.iloc[0]["records"]) == 0:
        return 0, {}
    row = frame.iloc[0]
    counts = {
        "BLUE": int(row["blue"]),
        "PURPLE": int(row["purple"]),
        "ORANGE": int(row["orange"]),
    }
    if include_green:
        counts = {"GREEN": int(row["green"]), **counts, "OTHER": int(row["unaccounted"])}
    return int(row["attempts"]), counts


def _date_controls() -> tuple[date, date]:
    today = date.today()
    columns = st.columns(2)
    start = columns[0].date_input("开始日期", value=date(2020, 1, 1))
    end = columns[1].date_input("结束日期", value=today)
    if start > end:
        st.error("开始日期不能晚于结束日期。")
    return start, end


def _run_controls(default_trials: int) -> tuple[int, int, int | None]:
    columns = st.columns(3)
    trials = int(columns[0].number_input(
        "每个模拟数据集的试验数", min_value=1, max_value=MAX_TRIALS,
        value=max(1, min(default_trials, MAX_TRIALS)), step=1,
    ))
    simulations = int(columns[1].selectbox(
        "独立模拟数据集数量", SIMULATION_OPTIONS,
        index=SIMULATION_OPTIONS.index(DEFAULT_SIMULATIONS),
    ))
    seed_mode = columns[2].radio("随机种子", ("自动生成并记录", "手动指定"))
    seed = None
    if seed_mode == "手动指定":
        seed = int(st.number_input("种子值", 0, MAX_SEED, 42, 1))
    return trials, simulations, seed


def _render_binary(result: BinaryMonteCarloResult) -> None:
    outcome = result.outcome
    columns = st.columns(5)
    columns[0].metric("模型期望", f"{outcome.expected:.3f}")
    columns[1].metric("模拟均值", f"{outcome.mean:.3f}")
    columns[2].metric("模拟中位数", f"{outcome.median:.3f}")
    columns[3].metric("模拟标准差", f"{outcome.std:.3f}")
    columns[4].metric("使用的随机种子", str(result.random_seed))
    st.dataframe(binary_summary_frame(result), hide_index=True, width="stretch")
    show_chart(binary_count_distribution_chart(result), "mc-binary-count")
    show_chart(binary_rate_distribution_chart(result), "mc-binary-rate")
    st.info(
        f"解释：{outcome.classification}。95% Monte Carlo 模拟区间是模型生成结果的"
        "经验 2.5%–97.5% 分位区间；Very unusual 使用中央 99%（0.5%–99.5%）区间判断。"
        "这些都不是参数置信区间。"
    )


def _render_multinomial(result: MultinomialMonteCarloResult) -> None:
    st.metric("使用的随机种子", str(result.random_seed))
    frame = multinomial_summary_frame(result)
    frame["category"] = frame["category"].map(lambda value: QUALITY_LABELS.get(value, value))
    st.dataframe(frame, hide_index=True, width="stretch")
    show_chart(multinomial_comparison_chart(result), "mc-multinomial")
    st.info(
        f"整体解释：{result.classification}。逐类别 95% 区间是模拟结果分位区间，"
        "Very unusual 使用中央 99%（0.5%–99.5%）区间判断；它们不是置信区间。"
        "类别之间因总数固定而相关。"
    )


def _render_actual_summary(inputs: dict[str, Any]) -> None:
    """Show actual data before simulation without turning no data into zero."""
    st.subheader("实际数据摘要")
    trials = inputs["actual_trials"]
    if not trials:
        st.info("No actual observations available. 当前选择没有实际观测，不会把实际结果记为 0。")
        return
    actual = inputs["actual"]
    if isinstance(inputs["probabilities"], dict):
        rows = []
        for category, probability in inputs["probabilities"].items():
            count = int(actual[category])
            rows.append({
                "category": QUALITY_LABELS.get(category, category),
                "target_probability": probability,
                "actual_count": count,
                "observed_rate": count / trials,
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        probability = inputs["probabilities"]
        columns = st.columns(4)
        columns[0].metric("Actual sample size", f"{trials:,}")
        columns[1].metric("实际橙品数", f"{int(actual):,}")
        columns[2].metric("Observed rate", f"{actual / trials:.3%}")
        columns[3].metric(
            "Target probability",
            "Not specified" if probability is None else f"{probability:.3%}",
        )


def _render_phase3_inference(inputs: dict[str, Any]) -> None:
    """Reuse Phase 3 tests and keep their p-values separate from simulation."""
    st.subheader("Phase 3 statistical inference（与 Monte Carlo 分开）")
    trials = inputs["actual_trials"]
    if not trials:
        st.caption("No actual observations available; no inferential test is calculated.")
        return
    probabilities = inputs["probabilities"]
    actual = inputs["actual"]
    if inputs["model_name"] == MATERIAL_EMPIRICAL_MODEL:
        st.caption("经验概率来自同一批观测；对同一数据执行拟合后检验不构成独立验证，因此不显示 p 值。")
        return
    if not isinstance(probabilities, dict):
        if probabilities is None:
            st.caption("尚未指定理论概率，因此没有 Phase 3 精确检验。")
            return
        test = calculate_binomial_test(int(actual), trials, probabilities)
        st.write(
            f"Exact binomial test：p={test.p_value:.6g}。"
            + interpret_p_value(test.p_value, f"橙品率等于目标值 {probabilities:.3%}")
        )
        return
    if "ORANGE" in probabilities:
        orange_test = calculate_binomial_test(
            int(actual["ORANGE"]), trials, probabilities["ORANGE"]
        )
        st.write(
            f"橙品 exact binomial test：p={orange_test.p_value:.6g}。"
            + interpret_p_value(
                orange_test.p_value,
                f"橙品率等于目标值 {probabilities['ORANGE']:.3%}",
            )
        )
    try:
        gof = calculate_chi_square_gof(
            [actual[category] for category in probabilities],
            list(probabilities.values()),
        )
        st.write(
            f"Pearson goodness-of-fit：χ²={gof.statistic:.4f}，"
            f"df={gof.degrees_of_freedom}，p={gof.p_value:.6g}。"
        )
    except ValueError as exc:
        st.caption(f"整体拟合优度检验未显示：{exc}")


def _material_inputs(start: date, end: date) -> dict[str, Any]:
    columns = st.columns(2)
    item = columns[0].selectbox("材料", MATERIALS)
    level = columns[1].selectbox("技能等级", SKILL_LEVELS)
    summary, _ = load_material_analysis(item, level, start, end)
    actual_trials = int(summary["attempts"].sum()) if not summary.empty else 0
    actual_successes = int(summary["orange"].sum()) if not summary.empty else 0
    st.caption("No theoretical probability target is configured for this material.")
    source = st.radio(
        "概率模型",
        (
            "Manual theoretical model — 用户指定概率（非官方）",
            "Empirical probability model — 当前筛选经验概率（非官方）",
        ),
    )
    if source.startswith("Manual"):
        entered_probability = st.number_input(
            "橙品理论概率 (%)", min_value=0.0, max_value=100.0,
            value=None, step=0.01, placeholder="必须明确输入",
        )
        probability = None if entered_probability is None else entered_probability / 100
        model_name = MATERIAL_USER_MODEL
    else:
        probability = actual_successes / actual_trials if actual_trials else 0.0
        model_name = MATERIAL_EMPIRICAL_MODEL
        st.caption("经验模型使用同一筛选数据估计概率，因此不应视为独立的模型验证。")
    return {
        "category": MATERIAL_PRODUCTION, "item": item, "level": level,
        "probabilities": probability, "model_name": model_name,
        "actual_trials": actual_trials, "actual": actual_successes,
        "empirical_source_trials": actual_trials,
    }


def _quality_inputs(system: str, start: date, end: date) -> dict[str, Any]:
    if system == "马厩品质":
        columns = st.columns(2)
        item = columns[0].selectbox("马匹", HORSE_BREEDS)
        level = columns[1].selectbox("技能等级", SKILL_LEVELS)
        summary, _, sessions = load_quality_analysis(HORSE_SEARCH, item, level, start, end)
        displayed = get_displayed_probabilities(HORSE_SEARCH)
        probabilities = literal_horse_probabilities(displayed)
        actual_trials, actual = _actual_quality_counts(summary, include_green=True)
        st.warning(HORSE_PROBABILITY_WARNING)
        st.caption("不归一化 99% 显示值；剩余 1% 明确建模为“其他 / 未说明”。")
        return {
            "category": HORSE_SEARCH, "item": item, "level": level,
            "probabilities": probabilities, "model_name": HORSE_LITERAL_MODEL,
            "actual_trials": actual_trials, "actual": actual, "sessions": sessions,
        }
    level = st.selectbox("技能等级", SKILL_LEVELS)
    summary, by_item, _ = load_quality_analysis(BIRD_RANDOM, None, level, start, end)
    if system == "灵禽品质":
        probabilities = get_displayed_probabilities(BIRD_RANDOM)
        actual_trials, actual = _actual_quality_counts(summary, include_green=False)
        return {
            "category": BIRD_RANDOM, "item": None, "level": level,
            "probabilities": probabilities, "model_name": BIRD_QUALITY_MODEL,
            "actual_trials": actual_trials, "actual": actual,
        }
    probabilities = {species: 0.25 for species in BIRD_SPECIES}
    actual = {species: 0 for species in BIRD_SPECIES}
    if not by_item.empty:
        for row in by_item.itertuples(index=False):
            if row.item in actual:
                actual[row.item] = int(row.attempts)
    actual_trials = sum(actual.values())
    st.caption("这是明确的等概率检验假设，不是官方概率，也不是从数据拟合的模型。")
    return {
        "category": BIRD_RANDOM, "item": None, "level": level,
        "probabilities": probabilities, "model_name": BIRD_EQUAL_SPECIES_MODEL,
        "actual_trials": actual_trials, "actual": actual,
    }


def _run_model(inputs: dict[str, Any], trials: int, simulations: int, seed: int | None):
    actual_trials = inputs["actual_trials"] or None
    actual = inputs["actual"] if actual_trials else None
    if isinstance(inputs["probabilities"], dict):
        return simulate_multinomial(
            inputs["probabilities"], trials, simulations, seed,
            actual_counts=actual, actual_trials=actual_trials,
        )
    return simulate_binary(
        inputs["probabilities"], trials, simulations, seed,
        actual_successes=actual, actual_trials=actual_trials,
    )


def _choose_actual_source(inputs: dict[str, Any]) -> dict[str, Any]:
    """Select filtered observations, manual comparison data, or no comparison."""
    mode = st.radio("实际结果来源", ("当前筛选观测", "手动输入", "不比较实际结果"), horizontal=True)
    selected = dict(inputs)
    if mode == "不比较实际结果":
        selected["actual_trials"] = 0
        selected["actual"] = {} if isinstance(inputs["probabilities"], dict) else 0
        selected["actual_source"] = "none"
        return selected
    if mode == "当前筛选观测":
        selected["actual_source"] = "current filtered observations"
        return selected
    selected["actual_source"] = "manual"
    if isinstance(inputs["probabilities"], dict):
        st.caption("手动计数之和作为实际试验数；各类别必须互斥且完整。")
        columns = st.columns(min(5, len(inputs["probabilities"])))
        counts = {}
        for index, category in enumerate(inputs["probabilities"]):
            counts[category] = int(columns[index % len(columns)].number_input(
                f"实际 {QUALITY_LABELS.get(category, category)} 数", 0, MAX_TRIALS, 0, 1,
                key=f"manual-{inputs['model_name']}-{category}",
            ))
        selected["actual"] = counts
        selected["actual_trials"] = sum(counts.values())
    else:
        columns = st.columns(2)
        actual_trials = int(columns[0].number_input(
            "实际试验数", 1, MAX_TRIALS, max(1, inputs["actual_trials"] or 1_000), 1,
        ))
        actual_successes = int(columns[1].number_input(
            "实际橙品数", 0, actual_trials, min(inputs["actual"] or 0, actual_trials), 1,
        ))
        selected["actual_trials"] = actual_trials
        selected["actual"] = actual_successes
    return selected


def _run_signature(inputs: dict[str, Any], start: date, end: date) -> tuple[Any, ...]:
    actual = inputs["actual"]
    actual_key = tuple(actual.items()) if isinstance(actual, dict) else actual
    probabilities = inputs["probabilities"]
    probability_key = (
        tuple(probabilities.items()) if isinstance(probabilities, dict) else probabilities
    )
    return (
        inputs["category"], inputs["model_name"], inputs["item"], inputs["level"],
        str(start), str(end), probability_key, inputs["actual_source"],
        inputs["actual_trials"], actual_key,
    )


def _render_horse_session(inputs: dict[str, Any], seed: int, simulations: int) -> dict[str, Any]:
    actual_sessions = inputs["sessions"]
    comparable = (
        actual_sessions.loc[actual_sessions["searches"] == 8, "orange"].to_numpy()
        if not actual_sessions.empty else None
    )
    result = simulate_binary(0.01, 8, simulations, (seed + 1) % (MAX_SEED + 1))
    frame = session_probability_frame(result, comparable)
    st.subheader("8 次搜索会话")
    st.caption("Monte Carlo 是对 Phase 3 精确二项结果的补充，不替代精确计算。")
    st.dataframe(frame, hide_index=True, width="stretch")
    show_chart(session_distribution_chart(frame), "mc-horse-session")
    return {
        "result": result.storage_dict(),
        "distribution": frame.to_dict(orient="records"),
        "actual_comparable_sessions": 0 if comparable is None else int(len(comparable)),
    }


def _save_current(inputs: dict[str, Any], result, extra: dict[str, Any] | None) -> int:
    payload = result.storage_dict()
    payload.update({
        "model_name": inputs["model_name"],
        "model_label": MODEL_LABELS[inputs["model_name"]],
        "actual_data_source": inputs["actual_source"],
    })
    if extra is not None:
        payload["horse_session_8_searches"] = extra
    probability = (
        result.target_probability if isinstance(result, BinaryMonteCarloResult)
        else float(dict(zip(result.categories, result.probabilities, strict=True)).get("ORANGE", result.probabilities[0]))
    )
    return save_simulation_run(
        inputs["category"], inputs["model_name"], probability,
        result.trial_count, result.simulation_count, result.random_seed, payload,
        inputs["item"], inputs["level"],
    )


def _history() -> None:
    st.header("模拟历史")
    history = load_simulation_history(30)
    if history.empty:
        st.caption("尚未保存模拟摘要。")
        return
    visible = history.drop(columns=["result_json"])
    st.dataframe(visible, hide_index=True, width="stretch")
    selected = st.selectbox("查看已保存摘要", history["id"].tolist())
    payload = history.loc[history["id"] == selected, "result_json"].iloc[0]
    st.json(payload)


def render() -> None:
    configure_page("Monte Carlo", "🎲")
    st.title("Monte Carlo 模拟实验室")
    st.caption("模型假设 → 生成独立数据集 → 与当前筛选观测比较 → 可选保存摘要")
    st.info(
        "Phase 3 从实际观测执行统计推断；Phase 4 在选定概率模型下模拟许多假想数据集。"
        "p 值与 Monte Carlo 百分位会分别展示，不合并为“置信分数”。"
    )
    system = st.selectbox("模型", ("官匠营橙品", "马厩品质", "灵禽品质", "灵禽种类等概率假设"))
    start, end = _date_controls()
    inputs = _material_inputs(start, end) if system == "官匠营橙品" else _quality_inputs(system, start, end)
    inputs = _choose_actual_source(inputs)
    signature = _run_signature(inputs, start, end)

    actual_trials = inputs["actual_trials"]
    _render_actual_summary(inputs)
    if actual_trials:
        st.success(f"当前筛选实际数据：{actual_trials:,} 次试验。")
    else:
        st.info("No actual observations available. 手动理论模拟仍可运行，但不会生成实际比较结论。")
    trials, simulations, seed = _run_controls(actual_trials or (8 if system == "马厩品质" else 1_000))
    if actual_trials and trials != actual_trials:
        st.warning("模拟试验数与实际试验数不同；会保留实际摘要，但不计算直接百分位或尾概率。")

    empirical_unavailable = (
        inputs["model_name"] == MATERIAL_EMPIRICAL_MODEL
        and not inputs.get("empirical_source_trials")
    )
    manual_probability_missing = (
        inputs["model_name"] == MATERIAL_USER_MODEL
        and inputs["probabilities"] is None
    )
    if empirical_unavailable:
        st.warning("当前筛选没有数据，无法构建经验概率模型；请选择用户指定理论概率或调整筛选。")
    if manual_probability_missing:
        st.warning("Manual theoretical model requires an explicit target probability.")
    if st.button(
        "运行 Monte Carlo", type="primary", width="stretch",
        disabled=empirical_unavailable or manual_probability_missing or start > end,
    ):
        with st.spinner("正在生成独立模拟数据集…"):
            result = _run_model(inputs, trials, simulations, seed)
        st.session_state["phase4_run"] = {
            "inputs": inputs, "result": result, "saved": False, "signature": signature,
        }

    state = st.session_state.get("phase4_run")
    if state and state["signature"] == signature:
        result = state["result"]
        st.header("模拟摘要与比较")
        if isinstance(result, BinaryMonteCarloResult):
            _render_binary(result)
        else:
            _render_multinomial(result)
            if inputs["model_name"] == BIRD_EQUAL_SPECIES_MODEL:
                st.write(
                    "How unusual is this species distribution under the equal-25% hypothesis? "
                    f"逐种类模拟比较的总体描述为：{result.classification}。"
                )
        _render_phase3_inference(inputs)
        extra = None
        if inputs["model_name"] == HORSE_LITERAL_MODEL:
            extra = _render_horse_session(inputs, result.random_seed, result.simulation_count)
        st.subheader("统计解释保护")
        st.caption(
            "经验百分位为 P(模拟数量 ≤ 实际数量)。双侧经验尾概率按“距模型期望至少与实际一样远”"
            "的模拟结果比例计算，并采用 +1 修正；它受 Monte Carlo 误差影响。模拟不证明独立性、"
            "平稳性或游戏机制，且不替代 Phase 3 的精确检验与置信区间。"
        )
        with st.expander("Monte Carlo limitations", expanded=False):
            st.write(
                "结果依赖所选理论模型；模拟不能证明模型正确。默认假设试验相互独立且概率固定。"
                "Monte Carlo 存在数值模拟误差；增加模拟次数可降低该误差，但不能修复错误的模型假设。"
                "100,000 次模拟表示 100,000 个独立的假想数据集，不等于 100,000 条真实观测。"
            )
        if st.button("保存此模拟摘要", disabled=state["saved"]):
            run_id = _save_current(inputs, result, extra)
            state["saved"] = True
            st.success(f"已保存模拟摘要 #{run_id}；未保存原始随机样本。")

    _history()


page_guard(render)
