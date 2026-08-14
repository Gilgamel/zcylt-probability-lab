"""Category-specific fast entry backed by the unified Observation table."""

from datetime import datetime, time
from uuid import uuid4

import streamlit as st

from config.settings import (
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
from database.db import session_scope
from database.repository import ProbabilityRepository
from services.validation import ObservationInput
from ui import configure_page, get_setting, load_observations, page_guard


def _save(record: ObservationInput) -> None:
    """Save one validated observation."""
    with session_scope() as session:
        ProbabilityRepository(session).add_observation(
            category_type=record.category_type,
            item_name=record.item,
            level=record.level,
            attempt_count=record.attempt_count,
            observed_at=record.observed_at,
            green_count=record.green_count,
            blue_count=record.blue_count,
            purple_count=record.purple_count,
            orange_count=record.orange_count,
            unaccounted_count=record.unaccounted_count,
            session_key=record.session_key,
            remark=record.remark,
        )


def _material_entry() -> None:
    """Render repeated-batch material entry."""
    default_quantity = int(get_setting("default_quantity", "18"))
    with st.form("material-entry", clear_on_submit=True):
        left, right = st.columns(2)
        material = left.selectbox("材料", MATERIALS)
        skill = right.selectbox("技能等级", SKILL_LEVELS)
        observed_date = st.date_input("日期", key="material-date")
        quantity = left.number_input("生产数量", min_value=1, value=default_quantity, step=1)
        orange = right.number_input("红/橙数量", min_value=0, value=0, step=1)
        with st.expander("可选：完整品质数量"):
            quality_columns = st.columns(4)
            green = quality_columns[0].number_input("绿品", min_value=0, value=0, step=1, key="material-green")
            blue = quality_columns[1].number_input("蓝品", min_value=0, value=0, step=1, key="material-blue")
            purple = quality_columns[2].number_input("紫品", min_value=0, value=0, step=1, key="material-purple")
            other = quality_columns[3].number_input("其他/未说明", min_value=0, value=0, step=1, key="material-other")
        remark = st.text_area("备注", max_chars=500, key="material-remark")
        submitted = st.form_submit_button("保存官匠营记录", type="primary", width="stretch")
    if submitted:
        record = ObservationInput(
            category_type=MATERIAL_PRODUCTION,
            item=material,
            level=skill,
            attempt_count=quantity,
            orange_count=orange,
            green_count=green,
            blue_count=blue,
            purple_count=purple,
            unaccounted_count=other,
            observed_at=datetime.combine(observed_date, time.min),
            remark=remark,
            session_key=uuid4().hex,
        )
        _save(record)
        st.success("官匠营记录已保存并累计。")


def _horse_entry() -> None:
    """Render full horse-search session entry."""
    st.warning(HORSE_PROBABILITY_WARNING)
    with st.form("horse-entry", clear_on_submit=True):
        left, right = st.columns(2)
        horse = left.selectbox("搜索前选择马匹", HORSE_BREEDS)
        level = right.number_input("等级", min_value=1, value=10, step=1)
        observed_date = st.date_input("日期", key="horse-date")
        searches = st.number_input("本次会话搜索次数", min_value=1, max_value=8, value=1, step=1)
        columns = st.columns(5)
        green = columns[0].number_input("绿品", min_value=0, value=0, step=1)
        blue = columns[1].number_input("蓝品", min_value=0, value=0, step=1)
        purple = columns[2].number_input("紫品", min_value=0, value=0, step=1)
        orange = columns[3].number_input("橙品", min_value=0, value=0, step=1)
        other = columns[4].number_input("其他/未说明", min_value=0, value=0, step=1)
        remark = st.text_area("备注", max_chars=500, key="horse-remark")
        submitted = st.form_submit_button("保存马厩会话", type="primary", width="stretch")
    if submitted:
        record = ObservationInput(
            category_type=HORSE_SEARCH,
            item=horse,
            level=level,
            attempt_count=searches,
            green_count=green,
            blue_count=blue,
            purple_count=purple,
            orange_count=orange,
            unaccounted_count=other,
            observed_at=datetime.combine(observed_date, time.min),
            remark=remark,
            session_key=uuid4().hex,
        )
        _save(record)
        st.success("马厩完整会话已保存并累计。")


def _bird_entry() -> None:
    """Render individual species + quality results without preselecting a target."""
    st.caption("灵禽种类是搜索结果，不是搜索前选择的目标。每次结果将保留为独立原始观测。")
    search_count = st.number_input(
        "本次记录搜索次数", min_value=1, max_value=8, value=1, step=1, key="bird-count"
    )
    with st.form("bird-entry", clear_on_submit=True):
        left, right = st.columns(2)
        level = left.number_input("等级", min_value=1, value=10, step=1, key="bird-level")
        observed_date = right.date_input("日期", key="bird-date")
        results: list[tuple[str, str]] = []
        quality_options = ("BLUE", "PURPLE", "ORANGE")
        for index in range(int(search_count)):
            species_col, quality_col = st.columns(2)
            species = species_col.selectbox(
                f"搜索 {index + 1} · 种类结果", BIRD_SPECIES, key=f"bird-species-{index}"
            )
            quality = quality_col.selectbox(
                f"搜索 {index + 1} · 品质结果",
                quality_options,
                format_func=lambda value: QUALITY_LABELS[value],
                key=f"bird-quality-{index}",
            )
            results.append((species, quality))
        remark = st.text_area("备注", max_chars=500, key="bird-remark")
        submitted = st.form_submit_button("保存灵禽结果", type="primary", width="stretch")
    if submitted:
        observed_at = datetime.combine(observed_date, time.min)
        session_key = uuid4().hex
        records = [
            ObservationInput(
                category_type=BIRD_RANDOM,
                item=species,
                level=level,
                attempt_count=1,
                blue_count=int(quality == "BLUE"),
                purple_count=int(quality == "PURPLE"),
                orange_count=int(quality == "ORANGE"),
                observed_at=observed_at,
                remark=remark,
                session_key=session_key,
            )
            for species, quality in results
        ]
        with session_scope() as session:
            repository = ProbabilityRepository(session)
            for record in records:
                repository.add_observation(
                    category_type=record.category_type,
                    item_name=record.item,
                    level=record.level,
                    attempt_count=record.attempt_count,
                    observed_at=record.observed_at,
                    green_count=record.green_count,
                    blue_count=record.blue_count,
                    purple_count=record.purple_count,
                    orange_count=record.orange_count,
                    unaccounted_count=record.unaccounted_count,
                    session_key=record.session_key,
                    remark=record.remark,
                )
        st.success(f"已保存 {len(records)} 次灵禽搜索结果。")


def _saved_status() -> None:
    """Show durable cumulative totals by category."""
    observations = load_observations()
    st.divider()
    st.subheader("累计保存状态")
    if observations.empty:
        st.info("数据库中还没有观测记录。")
        return
    grouped = observations.groupby("category", as_index=False).agg(
        记录数=("id", "count"),
        尝试次数=("attempt_count", "sum"),
        橙品数=("orange_count", "sum"),
    )
    st.dataframe(grouped, hide_index=True, width="stretch")
    recent = observations.head(10).copy()
    recent["日期"] = recent["observed_at"].dt.strftime("%Y-%m-%d")
    st.caption("最近保存的 10 条原始记录")
    st.dataframe(
        recent[["日期", "category", "item", "level", "attempt_count", "orange_count", "remark"]]
        .rename(columns={
            "category": "分类", "item": "项目/结果", "level": "等级",
            "attempt_count": "尝试次数", "orange_count": "橙品", "remark": "备注",
        }),
        hide_index=True,
        width="stretch",
    )


def render() -> None:
    """Render all category-specific entry workflows."""
    st.title("数据录入")
    material_tab, horse_tab, bird_tab = st.tabs(["官匠营", "马厩", "灵禽院"])
    with material_tab:
        _material_entry()
    with horse_tab:
        _horse_entry()
    with bird_tab:
        _bird_entry()
    _saved_status()


configure_page("数据录入", "✍️")
page_guard(render)
