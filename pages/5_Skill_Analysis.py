"""Focused skill comparison backed by the shared Phase 3 analysis service."""

import pandas as pd
import streamlit as st

from charts.statistical_charts import rate_with_ci_chart
from config.domain import MATERIALS
from services.analysis import comparison_table, complete_level_table, pairwise_level_comparisons
from ui import configure_page, load_material_analysis, page_guard, show_chart


OBSERVED_RATE_HELP = (
    "观测率 = 红色数量 ÷ 生产次数，按当前材料范围和技能等级汇总。"
    "它描述目前样本中实际观察到的比例，不等于游戏的真实概率或官方概率。"
    "例如 5 / 90 = 5.556%；0% 只表示当前样本尚未出现红色，不证明真实概率为 0。"
)

WILSON_CI_HELP = (
    "根据红色数量和生产次数计算的 95% Wilson 得分区间。"
    "它表示：若在相同条件下反复抽样并每次用同一方法构造区间，"
    "长期约 95% 的区间会覆盖真实概率。区间越窄，估计越精确；"
    "它不是“真实概率有 95% 机会位于此区间”。"
)

SAMPLE_QUALITY_HELP = (
    "样本质量同时依据生产次数 n 和 95% Wilson 区间完整宽度（上限减下限）判定：\n"
    "No Data：n = 0；\n"
    "Very Low：n < 30，或区间宽度 > 20 个百分点；\n"
    "Low：排除 Very Low 后，n < 100，或区间宽度 > 10 个百分点；\n"
    "Moderate：n ≥ 100，且区间宽度 > 5、≤ 10 个百分点；\n"
    "Good：n ≥ 100，且区间宽度 ≤ 5 个百分点。\n"
    "因此小样本即使暂时得到较窄区间，也不会被评为较高质量。"
)


def render() -> None:
    st.title("技能等级比较")
    selected = st.selectbox("材料范围", ("全部材料", *MATERIALS))
    grouped, _ = load_material_analysis(None if selected == "全部材料" else selected)
    levels = complete_level_table(grouped)
    display = levels.copy()
    display["观测率"] = display["rate"].map(lambda value: "No Data" if pd.isna(value) else f"{value:.3%}")
    display["95% Wilson CI"] = ["No Data" if pd.isna(low) else f"{low:.3%}–{high:.3%}" for low, high in zip(levels["ci_low"], levels["ci_high"])]
    st.dataframe(
        display[[
            "level", "trials", "successes", "观测率",
            "95% Wilson CI", "sample_quality",
        ]],
        column_config={
            "level": st.column_config.NumberColumn("技能等级", format="%d"),
            "trials": st.column_config.NumberColumn(
                "生产次数", format="%d",
                help="当前材料范围和技能等级下累计的实际生产次数。",
            ),
            "successes": st.column_config.NumberColumn(
                "红色数量", format="%d",
                help="生产结果中记录为红色的次数。",
            ),
            "观测率": st.column_config.TextColumn(
                "观测率", help=OBSERVED_RATE_HELP,
            ),
            "95% Wilson CI": st.column_config.TextColumn(
                "95% Wilson CI", help=WILSON_CI_HELP,
            ),
            "sample_quality": st.column_config.TextColumn(
                "样本质量", help=SAMPLE_QUALITY_HELP,
            ),
        },
        hide_index=True,
        width="stretch",
    )
    st.caption("将鼠标停留在列标题旁的问号上，可查看指标定义和样本质量分级范围。")
    show_chart(rate_with_ci_chart(levels, "level", "技能等级红色率"), "skill-level-ci")
    table = comparison_table(pairwise_level_comparisons(grouped))
    if table.empty:
        st.info("当前数据不足以完成预设等级比较。")
    else:
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption("同时展示原始 p 值与 Holm 校正 p 值；significant 依据校正值判断，α=0.05。")


configure_page("技能等级比较")
page_guard(render)
