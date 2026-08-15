"""Persistent simulation, display, and sample-sufficiency settings."""

import streamlit as st

from config.domain import (
    BIRD_RANDOM,
    HORSE_PROBABILITY_WARNING,
    HORSE_SEARCH,
    QUALITY_LABELS,
)
from database.db import session_scope
from database.repository import SettingsRepository
from ui import configure_page, get_displayed_probabilities, get_setting, page_guard


def render() -> None:
    """Render configurable application behavior and raw target references."""
    st.title("设置")
    with st.form("settings"):
        quantity = st.number_input(
            "官匠营默认生产数量", 1,
            value=int(get_setting("default_material_quantity", "18"))
        )
        iterations = st.number_input(
            "默认模拟次数", 100, 2_000_000,
            int(get_setting("default_monte_carlo_iterations", "100000")), 1000,
        )
        random_seed = st.number_input(
            "默认随机种子", 0, 2_147_483_647,
            int(get_setting("default_random_seed", "42")), 1,
        )
        themes = ("dark", "light")
        current = get_setting("theme", "dark")
        theme = st.selectbox(
            "Plotly 图表主题", themes,
            index=themes.index(current) if current in themes else 0,
        )
        st.subheader("样本充分性（绝对误差阈值）")
        st.caption("阈值按 A ≤ B ≤ C 配置，特别适用于约 1% 的稀有事件。")
        threshold_columns = st.columns(4)
        grade_a = threshold_columns[0].number_input(
            "A 阈值 (%)", 0.01, 20.0,
            float(get_setting("sufficiency_a_moe", "0.005")) * 100, 0.01,
        ) / 100
        grade_b = threshold_columns[1].number_input(
            "B 阈值 (%)", 0.01, 20.0,
            float(get_setting("sufficiency_b_moe", "0.010")) * 100, 0.01,
        ) / 100
        grade_c = threshold_columns[2].number_input(
            "C 阈值 (%)", 0.01, 20.0,
            float(get_setting("sufficiency_c_moe", "0.020")) * 100, 0.01,
        ) / 100
        target_margin = threshold_columns[3].number_input(
            "采集目标误差 (%)", 0.01, 20.0,
            float(get_setting("target_margin_of_error", "0.005")) * 100, 0.01,
        ) / 100
        submitted = st.form_submit_button("保存设置", type="primary")
    if submitted:
        if not grade_a <= grade_b <= grade_c:
            raise ValueError("样本评级阈值必须满足 A ≤ B ≤ C")
        with session_scope() as session:
            repository = SettingsRepository(session)
            values = {
                "default_material_quantity": quantity,
                "default_monte_carlo_iterations": iterations,
                "default_random_seed": random_seed,
                "theme": theme,
                "sufficiency_a_moe": grade_a,
                "sufficiency_b_moe": grade_b,
                "sufficiency_c_moe": grade_c,
                "target_margin_of_error": target_margin,
            }
            for key, value in values.items():
                repository.set(key, str(value))
        st.success("设置已保存。")

    st.divider()
    st.subheader("数据库中的官方显示概率参考")
    st.caption("这里只展示原始显示概率；观测、拟合与模拟概率在分析页中单独标识。")
    horse = get_displayed_probabilities(HORSE_SEARCH)
    bird = get_displayed_probabilities(BIRD_RANDOM)
    st.write("马厩：", {QUALITY_LABELS[key]: f"{value:.2%}" for key, value in horse.items()})
    st.warning(HORSE_PROBABILITY_WARNING)
    st.write("灵禽院：", {QUALITY_LABELS[key]: f"{value:.2%}" for key, value in bird.items()})


configure_page("设置", "⚙️")
page_guard(render)
