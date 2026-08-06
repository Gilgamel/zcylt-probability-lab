"""Persistent application settings."""

import streamlit as st

from database.db import session_scope
from database.repository import ProbabilityRepository
from ui import configure_page, get_setting, page_guard


def render() -> None:
    st.title("设置")
    with st.form("settings"):
        quantity = st.number_input("默认生产数量", 1, value=int(get_setting("default_quantity", "18")))
        iterations = st.number_input("默认模拟次数", 100, 2_000_000, int(get_setting("default_iterations", "100000")), 1000)
        themes = ("dark", "light")
        current = get_setting("theme", "dark")
        theme = st.selectbox("Plotly 图表主题", themes, index=themes.index(current) if current in themes else 0)
        if st.form_submit_button("保存设置", type="primary"):
            with session_scope() as session:
                repository = ProbabilityRepository(session)
                repository.set_setting("default_quantity", str(quantity))
                repository.set_setting("default_iterations", str(iterations))
                repository.set_setting("theme", theme)
            st.success("设置已保存。")


configure_page("设置", "⚙️")
page_guard(render)
