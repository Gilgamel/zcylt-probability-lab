"""Production data entry page."""

from datetime import datetime

import streamlit as st

from config.settings import MATERIALS, SKILL_LEVELS
from database.db import session_scope
from database.repository import ProbabilityRepository
from services.validation import ProductionInput
from ui import configure_page, get_setting, page_guard


def render() -> None:
    st.title("数据录入")
    default_quantity = int(get_setting("default_quantity", "18"))
    with st.form("entry", clear_on_submit=True):
        left, right = st.columns(2)
        material = left.selectbox("材料", MATERIALS)
        skill = right.selectbox("技能等级", SKILL_LEVELS)
        observed_date = left.date_input("日期")
        observed_time = right.time_input("时间")
        quantity = left.number_input("生产数量", min_value=1, value=default_quantity, step=1)
        red = right.number_input("红色数量", min_value=0, value=0, step=1)
        remark = st.text_area("备注", max_chars=500)
        submitted = st.form_submit_button("保存记录", type="primary", width="stretch")
    if submitted:
        record = ProductionInput(
            material=material, skill_level=skill, quantity=quantity, red_quantity=red,
            datetime=datetime.combine(observed_date, observed_time), remark=remark,
        )
        with session_scope() as session:
            ProbabilityRepository(session).add_log(
                record.material, record.skill_level, record.quantity, record.red_quantity,
                record.datetime, record.remark,
            )
        st.success("记录已保存。")


configure_page("数据录入", "✍️")
page_guard(render)
