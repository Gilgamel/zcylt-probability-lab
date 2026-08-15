# ProbabilityLab

《这城有良田》的个人概率研究工具，用于记录官匠营、马厩和灵禽院观测，进行统计估计、假设检验、Monte Carlo 模拟与备份恢复。

## 架构

- Streamlit 原生多页面 UI 与 Plotly 图表
- Neon PostgreSQL 持久化数据库
- SQLAlchemy 2.x ORM 与 `psycopg` 驱动
- 七张业务表：`categories`、`items`、`observations`、`probability_targets`、`skill_progressions`、`settings`、`simulation_runs`
- 短生命周期事务会话；Streamlit 只缓存 SQLAlchemy Engine，不缓存 Session
- Pydantic 输入验证、Loguru 服务端日志
- Pandas、NumPy、SciPy、Statsmodels 统计与向量化模拟

应用没有本地数据库回退。缺少配置或 Neon 暂时不可用时，页面会显示不可用状态并禁用数据库操作，不会把零记录误报成有效的空数据库。

## Neon 设置

1. 登录 Neon，创建 Project。
2. 在项目中创建 PostgreSQL 数据库和应用角色。
3. 从 Neon 的 Connect 页面复制连接信息。
4. 使用 SQLAlchemy `psycopg` 格式保存为 `DATABASE_URL`；连接必须启用 Neon 要求的 TLS 参数。
5. 不要把真实地址写入代码、文档或 Git。

示例格式（仅占位）：

```text
postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

Neon 计算资源休眠后，首次访问可能需要短暂唤醒。应用会对当前连接操作做一次有限重试，不会发送周期性保活或虚假流量。

## 本地开发

目标环境为 Python 3.13+。项目提供 [`.env.example`](.env.example)，但不会自动加载 `.env`；可由 shell、IDE 或部署平台注入变量。

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require'
streamlit run app.py
```

如使用本地 `.env`，复制模板后由你信任的环境加载器读取：

```bash
cp .env.example .env
```

`.env`、`secrets.toml` 和同类秘密文件均已加入 `.gitignore`。

## Streamlit Community Cloud 部署

1. 把代码推送到 GitHub，确认仓库中没有任何真实数据库凭据。
2. 在 Streamlit Community Cloud 创建应用。
3. 选择仓库、分支和入口文件 `app.py`。
4. 打开 App settings → Secrets。
5. 添加：

```toml
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require"
```

6. 保存并重启应用。
7. Dashboard 应显示“数据库状态：Connected”。
8. 新建一条测试观测，刷新页面并重启应用，确认记录仍存在。
9. 在数据管理页导出 CSV，删除临时测试记录并确认观测总数恢复。

## 数据库初始化

每次部署只会：

- 检查 PostgreSQL 连接；
- 创建尚不存在的表和索引；
- 插入缺失的分类、项目、显示概率和默认设置。

初始化不会删除表、清空观测、覆盖已有设置或构造替代数据源。后续结构变更应通过 Alembic 迁移完成。

默认种子包括：

- 官匠营：9 种材料；
- 马厩：4 种马匹及原始显示概率 `41% / 50% / 7% / 1%`；
- 灵禽院：4 种灵禽及显示品质概率 `79% / 20% / 1%`；
- 技能进阶参考：`9→10 = 200`、`10→11 = 800`、`11→12 = 1600`；
- 默认材料数量 18、马厩等级 10、灵禽等级 10、模拟次数 100,000、置信水平 0.95。

马厩原始显示值合计 99%，绝不静默归一化。模拟页提供：

- `Literal Displayed Probability Model`：显式加入 1% Other；
- `Normalized Displayed Probability Model`：仅用于模拟的归一化模型。

## CSV 导出

数据管理页可以导出当前筛选或全部原始观测。CSV 使用 UTF-8 BOM，
并保持稳定列顺序，便于 Excel 直接打开。

## 测试

默认测试覆盖配置失败关闭、PostgreSQL DDL 编译、输入验证、统计、模拟和备份验证：

```bash
python -m pytest -q
```

需要真实 PostgreSQL 的连接、建表、种子、CRUD、回滚和备份往返测试只使用显式的 `TEST_DATABASE_URL`，且数据库名称必须包含 `test`：

```bash
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/probabilitylab_test?sslmode=require'
python -m pytest -q
```

请勿把生产数据库地址用作 `TEST_DATABASE_URL`。
