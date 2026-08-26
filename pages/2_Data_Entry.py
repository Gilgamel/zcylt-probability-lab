"""Category-specific fast entry backed by the unified Observation table."""

from datetime import date, datetime, time

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
    SKILL_LEVELS,
)
from config.timezone import APPLICATION_TIMEZONE_NAME, application_today
from database.db import session_scope
from database.repository import ObservationRepository
from services.validation import (
    ObservationInput,
    validate_bird_counts,
    validate_horse_session,
    validate_material_entry,
)
from ui import configure_page, get_setting, load_observations, page_guard


def _save(record: ObservationInput) -> None:
    """Save one validated observation."""
    with session_scope() as session:
        ObservationRepository(session).add(
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
            session_id=record.session_id,
            remark=record.remark,
        )


def _save_many(records: list[ObservationInput]) -> None:
    """Save one complete session atomically."""
    with session_scope() as session:
        repository = ObservationRepository(session)
        for record in records:
            repository.add(
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
                session_id=record.session_id,
                remark=record.remark,
            )


def _material_entry(observed_date: date) -> None:
    """Render repeated-batch material entry."""
    default_quantity = int(get_setting("default_material_quantity", "18"))
    default_level = int(get_setting("default_material_level", "12"))
    with st.form("material-entry", clear_on_submit=True):
        left, right = st.columns(2)
        material = left.selectbox("材料", MATERIALS)
        skill = right.selectbox(
            "技能等级",
            SKILL_LEVELS,
            index=(
                SKILL_LEVELS.index(default_level)
                if default_level in SKILL_LEVELS
                else SKILL_LEVELS.index(12)
            ),
        )
        quantity = left.number_input("生产数量", min_value=1, value=default_quantity, step=1)
        red_count = right.number_input("红色数量", min_value=0, value=0, step=1)
        remark = st.text_area("备注", max_chars=500, key="material-remark")
        submitted = st.form_submit_button("保存官匠营记录", type="primary", width="stretch")
    if submitted:
        try:
            record = validate_material_entry(
                material=material, skill_level=skill, quantity=quantity,
                # The unified database column is named orange_count, but 官匠营
                # calls this outcome 红色 in the game-facing UI.
                orange_count=red_count, remark=remark,
                observed_at=datetime.combine(observed_date, time.min),
            )
        except ValueError as exc:
            st.error(f"无法保存：{exc}")
        else:
            _save(record)
            st.success(f"官匠营记录已保存并累计。会话：{str(record.session_id)[:8]}")


def _horse_entry(observed_date: date) -> None:
    """Render full horse-search session entry."""
    st.warning(HORSE_PROBABILITY_WARNING)
    with st.form("horse-entry", clear_on_submit=True):
        left, right = st.columns(2)
        horse = left.selectbox("搜索前选择马匹", HORSE_BREEDS)
        level = right.number_input(
            "等级", min_value=1, value=int(get_setting("default_horse_level", "10")), step=1
        )
        searches = st.number_input("本次会话搜索次数", min_value=1, max_value=8, value=8, step=1)
        columns = st.columns(5)
        green = columns[0].number_input("绿品", min_value=0, value=0, step=1)
        blue = columns[1].number_input("蓝品", min_value=0, value=0, step=1)
        purple = columns[2].number_input("紫品", min_value=0, value=0, step=1)
        orange = columns[3].number_input("橙品", min_value=0, value=0, step=1)
        other = columns[4].number_input("其他/未说明", min_value=0, value=0, step=1)
        remark = st.text_area("备注", max_chars=500, key="horse-remark")
        submitted = st.form_submit_button("保存马厩会话", type="primary", width="stretch")
    if submitted:
        try:
            record = validate_horse_session(
                horse=horse, level=level, search_count=searches,
                green_count=green, blue_count=blue, purple_count=purple,
                orange_count=orange, unaccounted_count=other, remark=remark,
                observed_at=datetime.combine(observed_date, time.min),
            )
        except ValueError as exc:
            st.error(f"无法保存：{exc}")
        else:
            _save(record)
            st.success(f"马厩完整会话已保存并累计。会话：{str(record.session_id)[:8]}")


def _bird_entry(observed_date: date) -> None:
    """Render compact random-cultivation counts by species and quality."""
    st.caption(
        "灵禽院仅记录随机培养。请填写各品种对应的蓝、紫、橙数量；"
        "数量合计须为 1–8，无需逐次选择结果。"
    )
    with st.form("bird-entry", clear_on_submit=True):
        level = st.number_input(
            "等级（默认 10）", min_value=1, value=int(get_setting("default_bird_level", "10")),
            step=1, key="bird-level"
        )
        headers = st.columns((2, 1, 1, 1, 1))
        for column, label in zip(headers, ("品种", "蓝品", "紫品", "橙品", "合计")):
            column.markdown(f"**{label}**")
        counts: dict[str, dict[str, int]] = {}
        total_attempts = 0
        for species in BIRD_SPECIES:
            columns = st.columns((2, 1, 1, 1, 1))
            columns[0].write(species)
            blue = int(columns[1].number_input(
                f"{species}蓝品", 0, 8, 0, 1,
                key=f"bird-{species}-blue", label_visibility="collapsed",
            ))
            purple = int(columns[2].number_input(
                f"{species}紫品", 0, 8, 0, 1,
                key=f"bird-{species}-purple", label_visibility="collapsed",
            ))
            orange = int(columns[3].number_input(
                f"{species}橙品", 0, 8, 0, 1,
                key=f"bird-{species}-orange", label_visibility="collapsed",
            ))
            species_total = blue + purple + orange
            columns[4].write(species_total)
            total_attempts += species_total
            counts[species] = {"BLUE": blue, "PURPLE": purple, "ORANGE": orange}
        st.caption(f"当前数量合计：{total_attempts} / 8")
        remark = st.text_area("备注", max_chars=500, key="bird-remark")
        submitted = st.form_submit_button("保存灵禽结果", type="primary", width="stretch")
    if submitted:
        try:
            records = validate_bird_counts(
                level=level,
                counts=counts,
                remark=remark,
                observed_at=datetime.combine(observed_date, time.min),
            )
        except ValueError as exc:
            st.error(f"无法保存：{exc}")
        else:
            _save_many(records)
            st.success(
                f"已保存 {sum(record.attempt_count for record in records)} 次随机培养结果，"
                f"汇总为 {len(records)} 条品种记录。"
                f"会话：{str(records[0].session_id)[:8]}"
            )


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
        目标品质数=("orange_count", "sum"),
    )
    st.dataframe(grouped, hide_index=True, width="stretch")
    recent = observations.head(10).copy()
    recent["日期"] = recent["observed_at"].dt.strftime("%Y-%m-%d")
    recent["会话"] = recent["session_id"].astype(str)
    recent["红色"] = recent["orange_count"].where(
        recent["category_type"] == MATERIAL_PRODUCTION
    )
    recent["橙品"] = recent["orange_count"].where(
        recent["category_type"] != MATERIAL_PRODUCTION
    )
    st.caption("最近保存的 10 条原始记录")
    st.dataframe(
        recent[["日期", "category", "item", "level", "attempt_count", "红色", "橙品", "会话", "remark"]]
        .rename(columns={
            "category": "分类", "item": "项目/结果", "level": "等级",
            "attempt_count": "尝试次数", "remark": "备注",
        }),
        hide_index=True,
        width="stretch",
    )


def render() -> None:
    """Render all category-specific entry workflows."""
    st.title("数据录入")
    selected_category = st.selectbox(
        "分类",
        (MATERIAL_PRODUCTION, HORSE_SEARCH, BIRD_RANDOM),
        format_func=lambda value: CATEGORIES[value],
    )
    observed_date = st.date_input(
        "记录日期",
        value=application_today(),
        help=f"只保存日期，不保存录入时间；默认按 {APPLICATION_TIMEZONE_NAME} 计算。",
    )
    if selected_category == MATERIAL_PRODUCTION:
        _material_entry(observed_date)
    elif selected_category == HORSE_SEARCH:
        _horse_entry(observed_date)
    else:
        _bird_entry(observed_date)
    _saved_status()


configure_page("数据录入")
page_guard(render)
