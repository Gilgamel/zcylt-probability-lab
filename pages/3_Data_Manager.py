"""Search, edit, delete, import, and export production records."""

import io

import pandas as pd
import streamlit as st

from config.settings import MATERIALS, SKILL_LEVELS
from database.db import session_scope
from database.repository import ProbabilityRepository
from services.validation import ProductionInput, validate_csv
from ui import configure_page, load_logs, page_guard


def render() -> None:
    st.title("数据管理")
    frame = load_logs()
    tab_records, tab_import = st.tabs(["记录管理", "CSV 导入 / 导出"])
    with tab_records:
        query = st.text_input("搜索材料或备注")
        filter_left, filter_right = st.columns(2)
        materials = filter_left.multiselect("材料筛选", MATERIALS)
        skills = filter_right.multiselect("技能筛选", SKILL_LEVELS)
        filtered = frame.copy()
        if query and not filtered.empty:
            mask = filtered["material"].str.contains(query, case=False, na=False) | filtered["remark"].str.contains(query, case=False, na=False)
            filtered = filtered[mask]
        if materials:
            filtered = filtered[filtered["material"].isin(materials)]
        if skills:
            filtered = filtered[filtered["skill_level"].isin(skills)]
        st.dataframe(filtered, width="stretch", hide_index=True)
        if not frame.empty:
            ids = frame["id"].astype(int).tolist()
            record_id = st.selectbox("选择记录 ID", ids)
            row = frame.loc[frame["id"] == record_id].iloc[0]
            with st.expander("编辑所选记录"):
                with st.form("edit"):
                    material = st.selectbox("材料", MATERIALS, index=MATERIALS.index(row["material"]))
                    skill = st.selectbox("技能等级", SKILL_LEVELS, index=SKILL_LEVELS.index(int(row["skill_level"])))
                    quantity = st.number_input("生产数量", 1, value=int(row["quantity"]))
                    red = st.number_input("红色数量", 0, value=int(row["red_quantity"]))
                    remark = st.text_input("备注", value=str(row["remark"] or ""))
                    if st.form_submit_button("保存修改", type="primary"):
                        ProductionInput(material=material, skill_level=skill, quantity=quantity, red_quantity=red, datetime=row["datetime"], remark=remark)
                        with session_scope() as session:
                            ProbabilityRepository(session).update_log(record_id, material=material, skill_level=skill, quantity=quantity, red_quantity=red, remark=remark)
                        st.success("修改已保存。")
                        st.rerun()
            if st.button("删除所选记录", type="secondary"):
                with session_scope() as session:
                    ProbabilityRepository(session).delete_log(record_id)
                st.success("记录已删除。")
                st.rerun()
    with tab_import:
        export = frame.drop(columns=["id"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
        st.download_button("导出全部 CSV", export, "probability_lab_export.csv", "text/csv")
        uploaded = st.file_uploader("导入 CSV", type=["csv"])
        if uploaded and st.button("验证并导入", type="primary"):
            imported = pd.read_csv(io.BytesIO(uploaded.getvalue()))
            records = validate_csv(imported)
            with session_scope() as session:
                repository = ProbabilityRepository(session)
                for record in records:
                    repository.add_log(record.material, record.skill_level, record.quantity, record.red_quantity, record.datetime, record.remark)
            st.success(f"成功导入 {len(records)} 条记录。")
            st.rerun()


configure_page("数据管理", "🗃️")
page_guard(render)
