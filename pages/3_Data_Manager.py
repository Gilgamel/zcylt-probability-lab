"""Search, edit, delete, and export unified raw observations."""

from datetime import datetime, time

import pandas as pd
import streamlit as st

from config.domain import (
    BIRD_RANDOM,
    BIRD_TARGETED,
    CATEGORIES,
    ITEMS_BY_CATEGORY,
    MATERIAL_PRODUCTION,
)
from config.timezone import application_today
from database.db import session_scope
from database.repository import ObservationRepository
from services.export import observation_csv_name, observations_csv_bytes
from services.security import delete_password_is_configured, verify_delete_password
from services.validation import ObservationInput
from ui import configure_page, load_observations, page_guard


DISPLAY_COLUMNS = (
    "记录 ID",
    "日期",
    "时间",
    "分类",
    "项目/结果",
    "等级",
    "尝试次数",
    "绿品",
    "蓝品",
    "紫品",
    "红色",
    "橙品",
    "其他/未说明",
    "会话 ID",
    "备注",
)


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Format the required manager columns without changing raw values."""
    displayed = pd.DataFrame(index=frame.index)
    displayed["记录 ID"] = frame["id"].astype(int)
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
    displayed["红色"] = frame["orange_count"].where(
        frame["category_type"] == MATERIAL_PRODUCTION
    )
    displayed["橙品"] = frame["orange_count"].where(
        frame["category_type"] != MATERIAL_PRODUCTION
    )
    displayed["其他/未说明"] = frame["unaccounted_count"]
    displayed["会话 ID"] = frame["session_id"].astype(str)
    displayed["备注"] = frame["remark"]
    return displayed.loc[:, DISPLAY_COLUMNS]


def _filter_records(frame: pd.DataFrame) -> pd.DataFrame:
    """Render filters and return the current result set."""
    query = st.text_input("搜索记录 ID、项目、备注或会话 ID")
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
        value=(application_today().replace(day=1), application_today()),
        disabled=not use_date_filter,
    )

    filtered = frame.copy()
    if query and not filtered.empty:
        record_id_text = filtered["id"].astype(str)
        session_text = filtered["session_id"].astype(str)
        mask = (
            record_id_text.str.contains(query, case=False, na=False)
            | filtered["item"].str.contains(query, case=False, na=False)
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
            "红色数量", min_value=0, value=int(row["orange_count"])
        )
    elif category_type in {BIRD_RANDOM, BIRD_TARGETED}:
        quality_columns = st.columns(3)
        blue = int(quality_columns[0].number_input(
            "蓝品", min_value=0, max_value=8, value=int(row["blue_count"])
        ))
        purple = int(quality_columns[1].number_input(
            "紫品", min_value=0, max_value=8, value=int(row["purple_count"])
        ))
        orange = int(quality_columns[2].number_input(
            "橙品", min_value=0, max_value=8, value=int(row["orange_count"])
        ))
        values.update({
            "attempt_count": blue + purple + orange,
            "blue_count": blue,
            "purple_count": purple,
            "orange_count": orange,
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


def _record_option_label(row: pd.Series) -> str:
    """Build a compact, human-readable selector label for one observation."""
    observed_date = pd.to_datetime(row["observed_at"]).strftime("%Y-%m-%d")
    remark = " ".join(str(row.get("remark") or "").split())
    if len(remark) > 24:
        remark = remark[:24] + "…"
    remark_part = f"｜备注：{remark}" if remark else ""
    return (
        f"ID {int(row['id'])}｜{observed_date}｜{row['category']}｜{row['item']}｜"
        f"等级 {int(row['level'])}｜数量 {int(row['attempt_count'])}{remark_part}"
    )


def _manage_one_record(filtered: pd.DataFrame) -> None:
    """Edit or explicitly confirm deletion of one filtered record."""
    if filtered.empty:
        return
    record_ids = filtered["id"].astype(int).tolist()
    option_labels = {
        int(row["id"]): _record_option_label(row)
        for _, row in filtered.iterrows()
    }
    record_id = st.selectbox(
        "选择要编辑或删除的记录",
        record_ids,
        format_func=lambda value: option_labels[int(value)],
    )
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

    st.subheader("删除所选记录")
    password_configured = delete_password_is_configured()
    if not password_configured:
        st.warning("删除功能尚未启用：请在 Streamlit Secrets 中配置 DELETE_PASSWORD。")
    delete_password = st.text_input(
        "删除密码",
        type="password",
        disabled=not password_configured,
        key=f"delete-password-{int(record_id)}",
    )
    confirm_delete = st.checkbox(
        f"我确认删除记录 ID {int(record_id)}；此操作不可撤销",
        disabled=not password_configured,
        key=f"confirm-delete-{int(record_id)}",
    )
    if st.button(
        "删除所选记录",
        disabled=not (password_configured and confirm_delete),
        type="primary",
    ):
        if not verify_delete_password(delete_password):
            st.error("删除密码错误，记录未删除。")
        else:
            with session_scope() as session:
                deleted = ObservationRepository(session).delete(int(record_id))
            if deleted:
                st.success("记录已删除。")
                st.rerun()
            else:
                st.error("记录不存在或已被删除。")


def _bulk_delete_records(filtered: pd.DataFrame) -> None:
    """Password-protect an atomic deletion of explicitly selected records."""
    if filtered.empty:
        return
    with st.expander("批量删除记录"):
        st.warning("批量删除不可撤销。建议先导出当前筛选 CSV 作为备份。")
        record_ids = filtered["id"].astype(int).tolist()
        option_labels = {
            int(row["id"]): _record_option_label(row)
            for _, row in filtered.iterrows()
        }
        select_all = st.checkbox(
            f"选择当前筛选结果中的全部 {len(record_ids)} 条记录",
            key="bulk-delete-select-all",
        )
        if select_all:
            selected_ids = record_ids
            st.caption(f"已选择全部 {len(selected_ids)} 条当前筛选记录。")
        else:
            selected_ids = st.multiselect(
                "选择要批量删除的记录",
                record_ids,
                format_func=lambda value: option_labels[int(value)],
                key="bulk-delete-ids",
            )

        if selected_ids:
            selected_set = {int(value) for value in selected_ids}
            preview = filtered[filtered["id"].astype(int).isin(selected_set)]
            st.caption(f"将删除 {len(selected_set)} 条记录，请核对以下内容：")
            st.dataframe(
                _display_frame(preview), hide_index=True, width="stretch"
            )

        password_configured = delete_password_is_configured()
        if not password_configured:
            st.warning("删除功能尚未启用：请在 Streamlit Secrets 中配置 DELETE_PASSWORD。")
        delete_password = st.text_input(
            "批量删除密码",
            type="password",
            disabled=not password_configured,
            key="bulk-delete-password",
        )
        confirm_delete = st.checkbox(
            f"我确认永久删除所选 {len(selected_ids)} 条记录",
            disabled=not (password_configured and selected_ids),
            key="bulk-delete-confirm",
        )
        if st.button(
            "批量删除所选记录",
            disabled=not (password_configured and selected_ids and confirm_delete),
            type="primary",
            key="bulk-delete-submit",
        ):
            if not verify_delete_password(delete_password):
                st.error("删除密码错误，未删除任何记录。")
            else:
                with session_scope() as session:
                    deleted_count = ObservationRepository(session).delete_many(
                        selected_ids
                    )
                st.success(f"已批量删除 {deleted_count} 条记录。")
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
    _bulk_delete_records(filtered)


configure_page("数据管理")
page_guard(render)
