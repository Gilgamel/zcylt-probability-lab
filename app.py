"""ProbabilityLab Streamlit entry point."""

import streamlit as st

from dashboard_view import render_dashboard
from ui import configure_page, page_guard


def dashboard_page() -> None:
    """Render the default dashboard page."""
    configure_page("仪表盘")
    page_guard(render_dashboard)


navigation = st.navigation(
    [
        st.Page(dashboard_page, title="仪表盘", default=True),
        st.Page("pages/2_Data_Entry.py", title="数据录入"),
        st.Page("pages/3_Data_Manager.py", title="数据管理"),
        st.Page("pages/4_Material_Analysis.py", title="官匠营分析"),
        st.Page("pages/5_Skill_Analysis.py", title="技能等级比较"),
        st.Page("pages/6_Horse_Analysis.py", title="马厩分析"),
        st.Page("pages/7_Bird_Analysis.py", title="灵禽院分析"),
        st.Page("pages/8_Monte_Carlo.py", title="蒙特卡洛模拟"),
        st.Page("pages/9_Settings.py", title="设置"),
    ]
)
navigation.run()
