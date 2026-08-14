"""Unified observation search, CRUD, and atomic CSV import/export."""

import io
from datetime import datetime, time

import pandas as pd
import streamlit as st

from config.domain import CATEGORIES, ITEMS_BY_CATEGORY, MATERIAL_PRODUCTION
from database.db import session_scope
from database.repository import ProbabilityRepository
from services.validation import ObservationInput, validate_csv, validate_observation_csv
from ui import configure_page, load_observations, page_guard


def _save_import(records: list[ObservationInput]) -> None:
    """Insert already validated records in one transaction."""
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


def render() -> None:
    """Render record management and CSV transfer workflows."""
    st.title("数据管理")
    frame = load_observations()
    records_tab, csv_tab = st.tabs(["记录管理", "CSV 导入 / 导出"])
    with records_tab:
        query = st.text_input("搜索项目或备注")
        category_names = st.multiselect("分类筛选", tuple(CATEGORIES.values()))
        filtered = frame.copy()
        if query and not filtered.empty:
            mask = (
                filtered["item"].str.contains(query, case=False, na=False)
                | filtered["remark"].str.contains(query, case=False, na=False)
            )
            filtered = filtered[mask]
        if category_names:
            filtered = filtered[filtered["category"].isin(category_names)]
        st.dataframe(filtered, hide_index=True, width="stretch")
        if frame.empty:
            st.info("暂无可管理的记录。")
        else:
            record_id = st.selectbox("选择记录 ID", frame["id"].astype(int).tolist())
            row = frame.loc[frame["id"] == record_id].iloc[0]
            category_type = str(row["category_type"])
            with st.expander("编辑所选记录"):
                st.caption(f"分类：{row['category']}（为保留语义，编辑时不可跨分类转换）")
                with st.form("edit-observation"):
                    observed_date = st.date_input("日期", value=row["observed_at"].date())
                    item_options = ITEMS_BY_CATEGORY[category_type]
                    item = st.selectbox(
                        "项目/结果", item_options, index=item_options.index(str(row["item"]))
                    )
                    level = st.number_input("等级", min_value=1, value=int(row["level"]))
                    attempts = st.number_input(
                        "尝试次数", min_value=1,
                        max_value=8 if category_type != MATERIAL_PRODUCTION else None,
                        value=int(row["attempt_count"]),
                    )
                    quality_columns = st.columns(5)
                    green = quality_columns[0].number_input("绿品", 0, value=int(row["green_count"]))
                    blue = quality_columns[1].number_input("蓝品", 0, value=int(row["blue_count"]))
                    purple = quality_columns[2].number_input("紫品", 0, value=int(row["purple_count"]))
                    orange = quality_columns[3].number_input("橙品", 0, value=int(row["orange_count"]))
                    other = quality_columns[4].number_input("其他", 0, value=int(row["unaccounted_count"]))
                    remark = st.text_input("备注", value=str(row["remark"] or ""))
                    submitted = st.form_submit_button("保存修改", type="primary")
                if submitted:
                    validated = ObservationInput(
                        category_type=category_type,
                        item=item,
                        level=level,
                        attempt_count=attempts,
                        green_count=green,
                        blue_count=blue,
                        purple_count=purple,
                        orange_count=orange,
                        unaccounted_count=other,
                        observed_at=datetime.combine(observed_date, time.min),
                        remark=remark,
                    )
                    with session_scope() as session:
                        ProbabilityRepository(session).update_observation(
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
                        )
                    st.success("修改已保存。")
                    st.rerun()
            if st.button("删除所选记录", type="secondary"):
                with session_scope() as session:
                    ProbabilityRepository(session).delete_observation(int(record_id))
                st.success("记录已删除。")
                st.rerun()

    with csv_tab:
        export_frame = frame.drop(columns=["id", "category"], errors="ignore")
        payload = export_frame.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "导出全部统一观测 CSV", payload, "probability_lab_observations.csv", "text/csv"
        )
        uploaded = st.file_uploader("导入 CSV", type=["csv"])
        if uploaded and st.button("验证并原子导入", type="primary"):
            imported = pd.read_csv(io.BytesIO(uploaded.getvalue()))
            if "category_type" in imported.columns:
                records = validate_observation_csv(imported)
            else:
                legacy = validate_csv(imported)
                records = [
                    ObservationInput(
                        category_type=MATERIAL_PRODUCTION,
                        item=record.material,
                        level=record.skill_level,
                        attempt_count=record.quantity,
                        orange_count=record.red_quantity,
                        observed_at=record.datetime,
                        remark=record.remark,
                    )
                    for record in legacy
                ]
            _save_import(records)
            st.success(f"成功导入 {len(records)} 条记录；文件中任一错误都会导致整批拒绝。")
            st.rerun()


configure_page("数据管理", "🗃️")
page_guard(render)
