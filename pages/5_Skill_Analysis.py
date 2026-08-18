"""Focused skill comparison backed by the shared Phase 3 analysis service."""

import pandas as pd
import streamlit as st

from charts.statistical_charts import rate_with_ci_chart
from config.domain import MATERIALS
from services.analysis import comparison_table, complete_level_table, pairwise_level_comparisons
from ui import configure_page, load_material_analysis, page_guard, show_chart


def render() -> None:
    st.title("技能等级比较")
    selected = st.selectbox("材料范围", ("全部材料", *MATERIALS))
    grouped, _ = load_material_analysis(None if selected == "全部材料" else selected)
    levels = complete_level_table(grouped)
    display = levels.copy()
    display["观测率"] = display["rate"].map(lambda value: "No Data" if pd.isna(value) else f"{value:.3%}")
    display["95% Wilson CI"] = ["No Data" if pd.isna(low) else f"{low:.3%}–{high:.3%}" for low, high in zip(levels["ci_low"], levels["ci_high"])]
    st.dataframe(display[["level", "trials", "successes", "观测率", "95% Wilson CI", "sample_quality"]], hide_index=True, width="stretch")
    show_chart(rate_with_ci_chart(levels, "level", "技能等级红色率"), "skill-level-ci")
    table = comparison_table(pairwise_level_comparisons(grouped))
    if table.empty:
        st.info("当前数据不足以完成预设等级比较。")
    else:
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption("同时展示原始 p 值与 Holm 校正 p 值；significant 依据校正值判断，α=0.05。")


configure_page("技能等级比较")
page_guard(render)
