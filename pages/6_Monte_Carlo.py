"""Monte Carlo simulation and automatic probability fitting."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import MATERIALS
from services.estimator import fit_probability
from services.simulator import ProductionSimulator
from ui import configure_page, get_setting, load_logs, page_guard, show_chart


def render() -> None:
    st.title("Monte Carlo 模拟")
    frame = load_logs()
    tab_simulate, tab_fit = st.tabs(["独立概率模拟", "自动拟合概率"])
    with tab_simulate:
        material = st.selectbox("材料", MATERIALS, key="sim-material")
        c1, c2, c3 = st.columns(3)
        probability = c1.number_input("概率 (%)", 0.0, 100.0, 3.0, 0.05) / 100
        quantity = c2.number_input("每次生产数量", 1, value=int(get_setting("default_quantity", "18")))
        iterations = c3.number_input("迭代次数", 100, 2_000_000, int(get_setting("default_iterations", "100000")), 1000)
        if st.button("运行模拟", type="primary", width="stretch"):
            with st.spinner("正在进行向量化模拟…"):
                values = ProductionSimulator(probability, int(quantity), int(iterations)).simulate()
            metrics = (("均值", values.mean()), ("中位数", np.median(values)), ("标准差", values.std()), ("最小值", values.min()), ("最大值", values.max()))
            for column, (label, value) in zip(st.columns(5), metrics):
                column.metric(label, f"{value:.3f}")
            figure = go.Figure()
            figure.add_histogram(x=values, name="模拟", opacity=0.72, histnorm="probability")
            real = frame[frame["material"] == material]["red_quantity"].to_numpy() if not frame.empty else np.array([])
            if real.size:
                figure.add_histogram(x=real, name="真实", opacity=0.62, histnorm="probability")
            figure.update_layout(barmode="overlay", title="模拟分布与真实数据", xaxis_title="每次红色数量", yaxis_title="比例")
            show_chart(figure, "simulation-result")
    with tab_fit:
        fit_material = st.selectbox("材料", MATERIALS, key="fit-material")
        c1, c2, c3 = st.columns(3)
        minimum = c1.number_input("最小概率 (%)", 0.0, 100.0, 2.5, 0.05)
        maximum = c2.number_input("最大概率 (%)", 0.0, 100.0, 4.0, 0.05)
        step = c3.number_input("步长 (%)", 0.01, 10.0, 0.05, 0.01)
        fit_iterations = st.number_input("每个候选迭代次数", 1000, 500_000, 50_000, 1000)
        if st.button("搜索最佳概率", type="primary"):
            observations = frame[frame["material"] == fit_material]["red_quantity"].to_numpy() if not frame.empty else np.array([])
            quantities = frame[frame["material"] == fit_material]["quantity"] if not frame.empty else pd.Series(dtype=int)
            fit_quantity = int(round(quantities.mean())) if not quantities.empty else int(get_setting("default_quantity", "18"))
            with st.spinner("正在比较候选概率…"):
                result = fit_probability(observations, fit_quantity, minimum / 100, maximum / 100, step / 100, int(fit_iterations))
            best = result.iloc[0]
            st.metric("最佳概率", f"{best['probability']:.3%}", help=f"误差分数：{best['error_score']:.6f}")
            top = result.head(10).copy()
            top["概率"] = top["probability"].map(lambda value: f"{value:.3%}")
            st.dataframe(top[["概率", "error_score", "simulated_mean"]].rename(columns={"error_score": "误差分数", "simulated_mean": "模拟均值"}), hide_index=True, width="stretch")


configure_page("Monte Carlo", "🎲")
page_guard(render)
