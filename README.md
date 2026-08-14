# ProbabilityLab

《这城有良田》的本地单人概率研究平台，覆盖官匠营、马厩和灵禽院。

## V1.1 功能

- 统一 `Category → Item → Observation` SQLAlchemy 数据模型
- SQLite 持久化、事务化 CRUD、搜索、筛选和原子 CSV 导入
- 官匠营材料及技能 9–12 分析
- 马厩完整品质与 1–8 次搜索会话分析
- 灵禽品质、种类分布和“品质 × 种类”分析
- Wilson 95% 置信区间、精确二项检验、卡方检验和比例 z 检验
- 可配置的绝对误差评级与追加样本量估计
- 官匠营二项模拟、马厩/灵禽多项模拟、真实分布叠加
- 三类系统的 Monte Carlo 概率拟合
- 固定随机种子和 SimulationRun 元数据保存
- Plotly 深色/浅色主题

## 马厩概率说明

数据库原样保存游戏显示的 `41% / 50% / 7% / 1%`，合计为 99%，不会静默归一化。

- 字面显示模式：显式添加剩余 1% 为 `Other / 未说明`
- 归一化模式：只在用户明确选择时用于模拟，并标注为“仅用于模拟的归一化概率”

显示概率、观测概率、拟合概率和 Monte Carlo 模拟概率在界面中分别标识。

## 运行

目标运行环境为 Python 3.13+：

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

首次启动会在 `data/probability.db` 创建并预置：

- 3 个分类
- 9 种材料、4 种马匹、4 种灵禽
- 马厩与灵禽院的原始显示概率
- 可配置的模拟和样本评级设置

旧版 `production_logs` 会一次性复制到统一 Observation 表，旧表不会删除，以保留原始观测。

## 统一 CSV

导出列：

```text
observed_at,category_type,item,level,attempt_count,
green_count,blue_count,purple_count,orange_count,
unaccounted_count,session_key,remark
```

仍兼容旧官匠营 CSV。任何一行验证失败时整批拒绝，并报告 CSV 源行号。

## 测试

```bash
pytest -q
```
