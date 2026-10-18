# OpenJobFlow 项目交接

更新日期：2026-10-18

本文件是新对话、换设备或暂停开发后的固定入口。先读本文件，再用代码、测试和 Git 实际结果确认状态；文档中的快照不能替代现场验证。

## 1. 当前项目身份

```text
项目名称：OpenJobFlow
公开仓库：Altriaqe/OpenJobFlow
当前分支：main
最近提交：新增架构总览并同步文档契约与 Ruff 基线（2026-10-18）
```

当前已提交到本地 `main`，领先 `origin/main` 1 个提交；尚未推送。具体提交号不看本文记录，以 `git log -1 --oneline` 和 `git status --short --branch` 的现场结果为准，避免文档自身提交后产生自引用偏差。

项目是公开开源的招聘数据 ETL、分析和报告投递系统。Python 包目录仍使用 `jobflow`，这是当前实现名称，不要为了文档整理做无关重命名。

## 2. 当前已验证状态

- 合规 JSON 快照可以经过 Adapter、ETL 和 PostgreSQL 分层存储；
- `ops`、`raw`、`core`、`mart` 四层职责已经形成；
- FastAPI 健康检查、就绪检查和固定分析接口已实现；
- 报告层支持确定性的 `query` 模式和可选的 AI 摘要模式；
- Telegram 图文投递已完成真实运行验证；
- 微信文章包生成和微信公众号待审核草稿已完成真实运行验证；
- Telegram 与微信使用独立状态和失败边界；
- 微信只自动创建草稿，正式发布由维护者在公众号后台人工审核；
- ETL 成功后，单个渠道失败不会回滚已经提交的数据或另一个已完成渠道；
- 每日任务包含登录/采集、API 就绪、ETL、报告和投递阶段的失败停止逻辑；
- Mihomo 只是受限网络下的可选部署组件，不是业务核心依赖。

这些结论表示功能和部分外部联调已经验证，不表示公网高可用、整机重启自动恢复、上游登录永不失效或长期无人值守稳定。

## 3. 公开文档入口

新对话按这个顺序阅读：

1. `docs/project-handoff.md`：当前停点和下一步；
2. `ARCHITECTURE.md`：根目录架构总览、组件契约、失败模型和验证入口；
3. `docs/architecture.md`：正式架构和边界（中文详细版）；
4. `docs/guides/ubuntu-deployment.md`：部署、每日任务和恢复规则；
5. `docs/guides/wechat-official-draft.md`：微信公众号草稿链路；
6. 相关代码、测试和最近提交：作为最终事实来源。

旧路径 `docs/reference/architecture.md` 仅是兼容入口，正式架构文档已改为 `docs/architecture.md`；根目录 `ARCHITECTURE.md` 是面向新读者的架构总览。

## 4. 代码与运行入口

```text
src/jobflow/adapters/       数据源校验与标准化
src/jobflow/workers/        ETL 编排和事务边界
src/jobflow/db/             PostgreSQL 连接、写入和分析 SQL
src/jobflow/api/            FastAPI 路由、鉴权和运行接口
src/jobflow/reports/        报告、趋势图和投递编排
src/jobflow/channels/       Telegram、微信测试号和公众号草稿
src/jobflow/operations/     运行检查和人工投递动作
ops/daily_update.sh         Ubuntu 每日任务入口
migrations/                 编号 SQL migration
compose.yaml                默认 Docker Compose 服务
compose.proxy.yaml          可选 Mihomo 覆盖配置
frontend/                   可选 React/Vite 操作界面
tests/                      单元、契约、API、运维和集成测试
```

每日主流程：

```text
systemd timer
→ ops/daily_update.sh
→ API 就绪检查
→ 快照/采集
→ ETL
→ Telegram 投递
→ 微信文章包
→ 微信公众号草稿
→ 人工审核发布
```

## 5. 重要行为约束

- 先查投递状态和外部后台，再处理不确定结果；不要因为接口超时就直接重复发送；
- Telegram 和微信必须分别核实，不能用一条链路的成功推断另一条成功；
- 微信失败不回滚 ETL 或 Telegram；
- 微信正式发布永远保留人工审核；
- 真实快照、`.env`、Token、Cookie、浏览器 Profile、代理订阅和服务器私有配置不得进入 Git；
- 公开文档只使用 `<SERVER_IP>`、`<JOBFLOW_DIR>` 等占位符；
- 任何外部采集都必须由部署者自行确认授权、平台条款和隐私要求。

## 6. 当前未完成事项

当前处于**稳定化观测阶段**，暂不安排 migration 升级、架构扩张或新功能开发。按优先级：

1. 继续观测连续多日运行、整机重启和异常投递，补齐验收证据；
2. 完善上游浏览器登录失效通知和人工恢复后的受控重跑；
3. 增加数据库备份、恢复演练、监控和告警；
4. migration 版本化增量升级暂缓；当前只保证初始化可重复执行，不宣称版本化升级能力；
5. 评估后续抓取范围、分析页面和公网部署，不提前视为已实现。

## 7. 本次交接变更

- 新增根目录 `ARCHITECTURE.md`：面向新读者的英文架构总览，覆盖分层、数据流、接口契约、失败模型、部署拓扑、验证与已知限制；
- 新增正式架构入口：`docs/architecture.md`；
- 旧架构路径保留为兼容入口；
- 交接文档改为当前状态优先，历史每日运行记录不再阻塞新对话阅读；
- 文档索引统一使用 `OpenJobFlow` 和传统职责命名；
- 根目录中英文 README 的仓库地址和架构链接统一到 `OpenJobFlow`；
- 文档测试契约同步到 OpenJobFlow 命名和 `guides/`、`reference/`、`development/`、`archive/` 目录结构，并改为只扫描被 Git 跟踪或未被忽略的公开文本；
- 固定 Ruff 规则集为 `E4, E7, E9, F`：此前 `pyproject.toml` 未写 `select`，新版本 Ruff 会自动扩大默认规则（实测 105 条），使 `ruff check` 结果随环境漂移；
- 新增 `.gitattributes`（文本文件统一换行为 LF），并对 `src/`、`tests/` 共 18 个 Python 文件执行 `ruff format`；
- `docs/` 在 Ruff 配置中排除格式化：历史计划和设计文档包含手写代码片段，不属于需要重新排版的源码。

## 8. 本次验证

- Python 3.12 虚拟环境运行 `pytest -q --ignore=tests/integration`：**401 passed、1 skipped**（skip 为 Windows 缺少 POSIX 权限位语义）；
- `pytest tests/docs -q`：13 项通过；
- `ruff check .`：All checks passed；
- `ruff format --check .`：133 files already formatted；
- `git diff --check`：无空白错误；
- 公开文档未写入凭据、真实地址、真实数据或私有路径；隐私扫描测试通过。

集成测试（`tests/integration/test_postgres_connection.py`）需要独立的 PostgreSQL 测试库和 `POSTGRES_HOST` 等环境变量，本机未配置，因此未在本轮运行；结果不构成对真实数据库行为的验收依据。

## 9. 新对话提示词

```text
这是 OpenJobFlow 项目。请先阅读 docs/project-handoff.md、ARCHITECTURE.md 和 docs/architecture.md，
再检查 git status --short --branch、git log -5 --oneline、相关代码和测试。
以代码、测试和 Git 为事实来源，不把历史计划写成已完成。
一次只推进一个可独立验收的小步骤；修改前先说明目标和影响范围。
不要把服务器私有配置、凭据、真实数据或外部账号信息写入公开仓库。
未经明确要求不要自动 commit 或 push。
```

## 10. 结束前检查

1. 更新本文件的当前状态、验证结果和下一步；
2. 架构边界变化时同步更新 `docs/architecture.md`；
3. 部署命令变化时同步更新对应运行指南；
4. 执行 `git diff --check` 和相关测试；
5. 检查公开文档没有凭据、真实地址、真实数据或私有路径；
6. 只有用户明确要求时才提交和推送。
