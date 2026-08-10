"""Production data entry page."""

from datetime import datetime, time

import streamlit as st

from config.settings import MATERIALS, SKILL_LEVELS
from database.db import session_scope
from database.repository import ProbabilityRepository
from services.validation import ProductionInput
from ui import configure_page, get_setting, load_logs, page_guard


def render() -> None:
    st.title("数据录入")
    default_quantity = int(get_setting("default_quantity", "18"))
    with st.form("entry", clear_on_submit=True):
        left, right = st.columns(2)
        material = left.selectbox("材料", MATERIALS)
        skill = right.selectbox("技能等级", SKILL_LEVELS)
        observed_date = st.date_input("日期")
        quantity = left.number_input("生产数量", min_value=1, value=default_quantity, step=1)
        red = right.number_input("红色数量", min_value=0, value=0, step=1)
        remark = st.text_area("备注", max_chars=500)
        submitted = st.form_submit_button("保存并累计", type="primary", width="stretch")
    if submitted:
        record = ProductionInput(
            material=material, skill_level=skill, quantity=quantity, red_quantity=red,
            datetime=datetime.combine(observed_date, time.min), remark=remark,
        )
        with session_scope() as session:
            ProbabilityRepository(session).add_log(
                record.material, record.skill_level, record.quantity, record.red_quantity,
                record.datetime, record.remark,
            )
        st.success("记录已保存并计入累计数据。")

    logs = load_logs()
    st.divider()
    st.subheader("累计保存状态")
    if logs.empty:
        st.info("数据库中还没有生产记录。")
        return

    total_quantity = int(logs["quantity"].sum())
    total_red = int(logs["red_quantity"].sum())
    metric_columns = st.columns(3)
    metric_columns[0].metric("已保存记录", f"{len(logs)} 条")
    metric_columns[1].metric("累计生产", total_quantity)
    metric_columns[2].metric(
        "累计红色",
        total_red,
        help=f"累计掉率：{total_red / total_quantity:.2%}",
    )

    recent = logs.head(10).copy()
    recent["日期"] = recent["datetime"].dt.strftime("%Y-%m-%d")
    recent = recent.rename(columns={
        "material": "材料",
        "skill_level": "技能等级",
        "quantity": "生产数量",
        "red_quantity": "红色数量",
        "remark": "备注",
    })
    st.caption("最近保存的 10 条记录")
    st.dataframe(
        recent[["日期", "材料", "技能等级", "生产数量", "红色数量", "备注"]],
        hide_index=True,
        width="stretch",
    )


configure_page("数据录入", "✍️")
page_guard(render)
