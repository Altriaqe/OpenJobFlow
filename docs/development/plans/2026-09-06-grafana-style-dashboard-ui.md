# Grafana 风格运行控制台 UI 改造计划

**目标：** 将现有 Streamlit 控制台改造成浅色、可扫描、可迁移的 Grafana 风格数据观测界面。

**架构：** 保留 Streamlit 作为当前渲染层，将数据查询、阶段状态映射、页面组件和 CSS 主题分离。组件只接收明确的数据对象，后续迁移 React 时复用阶段状态、运行记录和投放结果的数据契约。

**技术栈：** Python 3.12、Streamlit、现有 PostgreSQL 服务层、CSS tokens、pytest、Ruff。

## 约束

- 保留“平台总览”“运行中心”“投放中心”三个功能区。
- 删除“一键手动恢复运行”，避免重复执行每日采集和投放。
- Telegram 与微信公众号继续作为两个独立人工操作。
- 不复制竞品 Logo、文案、图片或像素级布局，只采用相近的信息架构和视觉语言。
- 不把 Token、外部 ID、私有路径或凭据写入页面和日志。
- 业务操作继续通过现有服务函数和数据库幂等边界执行。
- 页面在桌面和窄屏下都可用。

## 文件分工

- 修改 `src/jobflow/dashboard/app.py`：保留入口和业务编排，改为调用页面组件。
- 新建 `src/jobflow/dashboard/theme.py`：集中 CSS tokens、状态颜色和通用页面样式。
- 新建 `src/jobflow/dashboard/components.py`：指标卡、阶段表、趋势图、运行记录和投放操作组件。
- 修改 `tests/dashboard/test_dashboard_contract.py`：验证页面结构、安全边界和组件可导入。
- 新建 `tests/dashboard/test_components.py`：验证纯数据到展示模型的转换，不启动 Streamlit 服务。
- 修改 `docs/project-handoff.md`：记录 UI 改造完成边界和仍需服务器复验的内容。

## 实施步骤

### 1. 建立展示数据模型和纯函数

新增 `DashboardMetric`、`StageRow`、`RunRow` 数据类，以及 `build_stage_rows`、`build_metric_rows` 等无副作用函数。输入只使用现有 `StageSnapshot`、`CheckResult` 和数据库查询结果，输出可直接被 Streamlit 或未来 React 组件消费的普通数据对象。

### 2. 建立主题层

在 `theme.py` 中定义浅色背景、深色导航、蓝色主色、绿色成功、黄色观察、红色异常等 CSS tokens。通过单个 `inject_theme()` 注入页面样式，避免样式散落在业务函数中。

### 3. 拆分页面组件

在 `components.py` 中实现：

- `render_sidebar(active_page)`
- `render_topbar()`
- `render_metric_grid(metrics)`
- `render_stage_panel(rows)`
- `render_trend_panel(data)`
- `render_recent_runs(rows)`
- `render_delivery_actions(connection, authenticated)`

组件只负责渲染和接收回调，不直接拼接 SQL，不读取环境变量中的秘密值。

### 4. 重组入口页面

让 `app.py` 负责连接数据库、组装展示数据、调用组件和执行现有操作。移除“手动恢复运行”按钮及 `_run_recovery()` 调用；保留服务器检查、Telegram 单独操作和微信公众号草稿单独操作。

### 5. 增加回归测试

验证：

- 三个功能区仍存在。
- “手动恢复运行”不存在。
- 两个独立投放入口仍存在。
- 页面源码不含直接 SQL 和私有服务器路径。
- 状态映射可生成八个阶段。
- 组件模块可在无 Streamlit 浏览器会话下导入。

### 6. 本地验证与部署复验

运行：

```bash
pytest -q tests/dashboard tests/operations
ruff check src tests
ruff format --check src/jobflow/dashboard tests/dashboard
git diff --check
```

服务器只在本地验证通过后更新。更新后通过 SSH 隧道打开 Dashboard，检查页面布局、窄屏显示和两个独立投放按钮；不重复执行当天已经完成的投放。
