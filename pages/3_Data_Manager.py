"""Search, edit, delete, and export unified raw observations."""

from datetime import date, datetime, time

import pandas as pd
import streamlit as st

from config.domain import (
    BIRD_RANDOM,
    CATEGORIES,
    ITEMS_BY_CATEGORY,
    MATERIAL_PRODUCTION,
    QUALITY_LABELS,
)
from database.db import session_scope
from database.repository import ObservationRepository
from services.export import observation_csv_name, observations_csv_bytes
from services.validation import ObservationInput
from ui import configure_page, load_observations, page_guard


DISPLAY_COLUMNS = (
    "日期",
    "时间",
    "分类",
    "项目/结果",
    "等级",
    "尝试次数",
    "绿品",
    "蓝品",
    "紫品",
    "橙品",
    "其他/未说明",
    "会话 ID",
    "备注",
)


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Format the required manager columns without changing raw values."""
    displayed = pd.DataFrame(index=frame.index)
    displayed["日期"] = pd.to_datetime(frame["observed_at"]).dt.strftime("%Y-%m-%d")
    created = pd.to_datetime(frame["created_at"], errors="coerce")
    displayed["时间"] = created.dt.strftime("%H:%M:%S").fillna("")
    displayed["分类"] = frame["category"]
    displayed["项目/结果"] = frame["item"]
    displayed["等级"] = frame["level"]
    displayed["尝试次数"] = frame["attempt_count"]
    displayed["绿品"] = frame["green_count"]
    displayed["蓝品"] = frame["blue_count"]
    displayed["紫品"] = frame["purple_count"]
    displayed["橙品"] = frame["orange_count"]
    displayed["其他/未说明"] = frame["unaccounted_count"]
    displayed["会话 ID"] = frame["session_id"].astype(str)
    displayed["备注"] = frame["remark"]
    return displayed.loc[:, DISPLAY_COLUMNS]


def _filter_records(frame: pd.DataFrame) -> pd.DataFrame:
    """Render filters and return the current result set."""
    query = st.text_input("搜索项目、备注或会话 ID")
    category_names = st.multiselect("分类筛选", tuple(CATEGORIES.values()))
    item_options = sorted(frame["item"].dropna().unique().tolist()) if not frame.empty else []
    selected_items = st.multiselect("项目筛选", item_options)
    level_options = (
        sorted(frame["level"].dropna().astype(int).unique().tolist())
        if not frame.empty else []
    )
    selected_levels = st.multiselect("等级筛选", level_options)
    session_options = (
        sorted(frame["session_id"].dropna().astype(str).unique().tolist())
        if not frame.empty else []
    )
    selected_sessions = st.multiselect("会话筛选", session_options)
    use_date_filter = st.checkbox("启用日期范围筛选")
    selected_dates = st.date_input(
        "日期范围",
        value=(date.today().replace(day=1), date.today()),
        disabled=not use_date_filter,
    )

    filtered = frame.copy()
    if query and not filtered.empty:
        session_text = filtered["session_id"].astype(str)
        mask = (
            filtered["item"].str.contains(query, case=False, na=False)
            | filtered["remark"].str.contains(query, case=False, na=False)
            | session_text.str.contains(query, case=False, na=False)
        )
        filtered = filtered[mask]
    if category_names:
        filtered = filtered[filtered["category"].isin(category_names)]
    if selected_items:
        filtered = filtered[filtered["item"].isin(selected_items)]
    if selected_levels:
        filtered = filtered[filtered["level"].isin(selected_levels)]
    if selected_sessions:
        filtered = filtered[filtered["session_id"].astype(str).isin(selected_sessions)]
    if use_date_filter and isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        observed_dates = pd.to_datetime(filtered["observed_at"]).dt.date
        filtered = filtered[
            (observed_dates >= selected_dates[0]) & (observed_dates <= selected_dates[1])
        ]
    return filtered


def _edit_fields(row: pd.Series) -> dict[str, object]:
    """Render category-aware edit fields and return normalized UI values."""
    category_type = str(row["category_type"])
    observed_date = st.date_input("日期", value=row["observed_at"].date())
    item_options = ITEMS_BY_CATEGORY[category_type]
    item = st.selectbox(
        "项目/结果", item_options, index=item_options.index(str(row["item"]))
    )
    level = st.number_input("等级", min_value=1, value=int(row["level"]))
    values: dict[str, object] = {
        "category_type": category_type,
        "item": item,
        "level": level,
        "observed_at": datetime.combine(observed_date, time.min),
        "session_id": row["session_id"],
    }
    if category_type == MATERIAL_PRODUCTION:
        values["attempt_count"] = st.number_input(
            "生产数量", min_value=1, value=int(row["attempt_count"])
        )
        values["orange_count"] = st.number_input(
            "红/橙数量", min_value=0, value=int(row["orange_count"])
        )
    elif category_type == BIRD_RANDOM:
        values["attempt_count"] = 1
        qualities = ("BLUE", "PURPLE", "ORANGE")
        current = next(
            (quality for quality in qualities if int(row[f"{quality.lower()}_count"]) == 1),
            "BLUE",
        )
        quality = st.selectbox(
            "品质结果", qualities, index=qualities.index(current),
            format_func=lambda value: QUALITY_LABELS[value],
        )
        values.update({
            "blue_count": int(quality == "BLUE"),
            "purple_count": int(quality == "PURPLE"),
            "orange_count": int(quality == "ORANGE"),
        })
    else:
        values["attempt_count"] = st.number_input(
            "搜索次数", min_value=1, max_value=8, value=int(row["attempt_count"])
        )
        quality_columns = st.columns(5)
        for column, label, target in zip(
            quality_columns,
            ("绿品", "蓝品", "紫品", "橙品", "其他/未说明"),
            ("green_count", "blue_count", "purple_count", "orange_count", "unaccounted_count"),
        ):
            values[target] = column.number_input(
                label, min_value=0, value=int(row[target])
            )
    values["remark"] = st.text_input("备注", value=str(row["remark"] or ""))
    return values


def _manage_one_record(filtered: pd.DataFrame) -> None:
    """Edit or explicitly confirm deletion of one filtered record."""
    if filtered.empty:
        return
    record_ids = filtered["id"].astype(int).tolist()
    record_id = st.selectbox("选择记录 ID", record_ids)
    row = filtered.loc[filtered["id"] == record_id].iloc[0]
    with st.expander("编辑所选记录"):
        st.caption(
            f"分类：{row['category']} · 会话：{row['session_id']} · "
            "编辑保留记录 ID 和会话 ID。"
        )
        with st.form("edit-observation"):
            values = _edit_fields(row)
            submitted = st.form_submit_button("保存修改", type="primary")
        if submitted:
            try:
                validated = ObservationInput.model_validate(values)
            except ValueError as exc:
                st.error(f"无法保存修改：{exc}")
            else:
                with session_scope() as session:
                    ObservationRepository(session).update(
                        int(record_id),
                        item=validated.item,
                        observed_at=validated.observed_at,
                        level=validated.level,
                        attempt_count=validated.attempt_count,
                        green_count=validated.green_count,
                        blue_count=validated.blue_count,
                        purple_count=validated.purple_count,
                        orange_count=validated.orange_count,
                        unaccounted_count=validated.unaccounted_count,
                        remark=validated.remark,
                        session_id=validated.session_id,
                    )
                st.success("修改已保存；记录 ID 与会话 ID 保持不变。")
                st.rerun()

    confirm_delete = st.checkbox(
        f"我确认删除记录 ID {int(record_id)}；此操作不可撤销",
        key=f"confirm-delete-{int(record_id)}",
    )
    if st.button("删除所选记录", disabled=not confirm_delete):
        with session_scope() as session:
            ObservationRepository(session).delete(int(record_id))
        st.success("记录已删除。")
        st.rerun()


def render() -> None:
    """Render Phase 2 raw-data management."""
    st.title("数据管理")
    frame = load_observations()
    filtered = _filter_records(frame)
    st.caption(f"当前显示 {len(filtered)} / {len(frame)} 条原始记录")
    if filtered.empty:
        st.info("当前筛选条件下暂无记录。")
    else:
        st.dataframe(_display_frame(filtered), hide_index=True, width="stretch")

    export_left, export_right = st.columns(2)
    export_left.download_button(
        "导出当前筛选 CSV",
        observations_csv_bytes(filtered),
        observation_csv_name("filtered"),
        "text/csv",
        disabled=filtered.empty,
        width="stretch",
    )
    export_right.download_button(
        "导出全部 CSV",
        observations_csv_bytes(frame),
        observation_csv_name("all"),
        "text/csv",
        disabled=frame.empty,
        width="stretch",
    )
    st.divider()
    _manage_one_record(filtered)


configure_page("数据管理", "🗃️")
page_guard(render)
