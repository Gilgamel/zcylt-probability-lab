# ProbabilityLab

“这城有良田”生产掉率记录、统计分析与 Monte Carlo 模拟工具。

## 功能

- SQLite 持久化、完整 CRUD、搜索与筛选
- 严格验证的原子化 CSV 导入和完整导出
- 按材料与技能等级分析掉率、Wilson 95% 置信区间和样本质量
- 二项检验、卡方检验、比例 z 检验服务
- 支持 100,000 次以上的向量化 Monte Carlo 模拟
- 自动搜索最符合真实观察的候选概率
- Plotly 深色/浅色图表

## 运行

需要 Python 3.13+：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

数据库会在首次启动时自动创建于 `data/probability.db`，并预置九种材料和默认设置。

## CSV 格式

必需列：`datetime, material, skill_level, quantity, red_quantity`。可选列：`remark`。
任意一行验证失败时整个文件都会拒绝导入，并显示源 CSV 的行号。

## 测试

```bash
pytest -q
```
