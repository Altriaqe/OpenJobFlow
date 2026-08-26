# 微信公众号每日推送实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有抓取与 Telegram 语义的前提下，为 OpenJobFlow V1.3.2 增加可选的微信测试号模板推送、公众号文章排版包和独立投递状态，并在功能确认可行前保持不提交、不推送。

**Architecture:** 统一日报构建器产出渠道无关的聚合数据；Telegram 与微信作为独立、可并行的渠道消费该数据并分别记录状态。微信测试号只发送模板摘要，正式个人订阅号先生成 Markdown/HTML/PNG/manifest 排版包供人工发布。

**Tech Stack:** Python 3.12、FastAPI、Requests、PostgreSQL、SQL migration、Bash/systemd、Pytest、Matplotlib、Docker Compose。

## Global Constraints

- 真实 `appsecret`、`openid`、模板 ID、Token、Cookie、服务器地址和个人路径不得写入 Git、日志、测试、文档或文章包。
- Telegram 与微信跨渠道可并行；数据库锁只阻止同一渠道同一天重复发送。
- `uncertain` 结果禁止自动重试，只有人工确认未收到后才允许显式补发。
- 默认 `WECHAT_ENABLED=false`，不配置微信时现有 Docker Quick Start 和 Telegram 流程必须保持可用。
- 文章只展示固定范围聚合数据和趋势图，不展示原始岗位明细、公司名或岗位链接。
- 正式个人订阅号首版只生成文章排版包，不实现浏览器自动化或未经确认的发布 API。
- V1.3.2 在本机和 Docker 验证通过、测试号可行性确认前，不提交、不推送公开仓库。
- Ubuntu 服务器联调命令由用户执行；实施阶段只完成本机、Docker 和离线测试。

---

## 文件与职责映射

- Create: `src/jobflow/channels/wechat_official.py` — 微信配置、令牌、模板发送和脱敏回执。
- Create: `src/jobflow/reports/wechat_article.py` — Markdown/HTML/PNG/manifest 文章包生成。
- Modify: `src/jobflow/reports/multi_keyword_service.py` — 暴露统一、确定性的日报聚合对象。
- Create: `migrations/009_add_report_channel_deliveries.sql` — 渠道独立状态表和唯一约束。
- Create: `src/jobflow/db/report_deliveries.py` — 状态认领、转换和查询。
- Modify: `src/jobflow/api/reports.py` — 微信发送、状态和显式补发接口。
- Modify: `ops/daily_update.sh` — 文章包生成及 Telegram/微信并行执行、退出码汇总。
- Modify: `.env.example`, `compose.yaml`, `README.md`, `README.zh-CN.md` — 占位配置、功能介绍和教程链接。
- Create: `docs/wechat-test-account.md` — 测试号配置与人工验收教程，不包含真实值。
- Modify: `docs/project-handoff.md` — 记录实现状态和服务器联调边界。
- Create/Modify tests under `tests/channels`, `tests/reports`, `tests/db`, `tests/api`, `tests/ops` — 离线契约、并发和脚本测试。

## Task 1: 微信渠道离线适配器 ✅

**Files:**
- Create: `src/jobflow/channels/wechat_official.py`
- Test: `tests/channels/test_wechat_official.py`

**Interfaces:**
- Produces `get_wechat_access_token`, `send_wechat_template`, `WechatReceipt`, `WechatConfigurationError`, `WechatTokenError`, `WechatDeliveryError`, `WechatDeliveryUncertain`。
- Consumes只读配置对象和注入的 HTTP transport；不访问数据库。

- [x] Step 1: 为缺少配置、成功回执、明确错误和超时分别写失败测试。
- [x] Step 2: 运行 `python -m pytest tests/channels/test_wechat_official.py -q`，确认新接口尚未实现导致失败。
- [x] Step 3: 实现最小请求逻辑：固定官方 HTTPS 地址、限制令牌重试次数、对异常信息做变量名级脱敏。
- [x] Step 4: 重新运行该测试文件，预期全部通过。
- [ ] Step 5: 运行 `python -m ruff check src/jobflow/channels/wechat_official.py tests/channels/test_wechat_official.py`（当前 Python 3.11 环境未安装 ruff，待使用项目 Python 3.12 环境补跑）。

## Task 2: 统一日报与公众号文章包 ✅

**Files:**
- Modify: `src/jobflow/reports/multi_keyword_service.py`
- Create: `src/jobflow/reports/wechat_article.py`
- Test: `tests/reports/test_wechat_article.py`

**Interfaces:**
- Produces `build_multi_keyword_report(snapshot_date) -> MultiKeywordReport` 和 `write_wechat_article(report, output_dir) -> ArticleManifest`。
- `ArticleManifest` 必须列出 `article.md`、`article.html`、`trend.png`、`manifest.json` 四个相对路径。

- [ ] Step 1: 写测试覆盖无前日基线、周日完整基线、四关键词口径、HTML 无脚本和敏感字段。
- [ ] Step 2: 运行 `python -m pytest tests/reports/test_wechat_article.py -q`，确认失败。
- [ ] Step 3: 抽出纯聚合函数，生成模板字段和文章字段；使用临时目录后 `os.replace` 原子替换。
- [ ] Step 4: 重新运行测试并检查 `runtime/` 不产生 Git 未跟踪文件。
- [ ] Step 5: 运行现有报告测试：`python -m pytest tests/reports -q`。

## Task 3: 渠道投递状态与 API ✅

**Files:**
- Create: `migrations/009_add_report_channel_deliveries.sql`
- Create: `src/jobflow/db/report_deliveries.py`
- Modify: `src/jobflow/api/reports.py`
- Test: `tests/db/test_report_deliveries.py`, `tests/api/test_reports_wechat.py`

**Interfaces:**
- `claim_delivery(report_date, report_key, channel) -> DeliveryClaim`。
- `mark_sent`, `mark_failed`, `mark_uncertain` 使用同一唯一键。
- API：`POST /reports/daily/multi/wechat/send`、`GET /reports/daily/multi/wechat/status`、`POST /reports/daily/multi/wechat/resend?confirm_not_received=true`。

- [ ] Step 1: 为唯一约束、并发认领、`already_sent`、`uncertain` 拒绝普通发送写测试。
- [ ] Step 2: 运行 `python -m pytest tests/db/test_report_deliveries.py tests/api/test_reports_wechat.py -q`，确认失败。
- [ ] Step 3: 添加 migration 和行锁事务；实现 API Bearer Token 校验及状态映射。
- [ ] Step 4: 重新运行数据库/API 测试，并运行 `python -m pytest tests/api -q`。
- [ ] Step 5: 使用 `git diff --check` 检查 SQL、Python 和路由变更。

## Task 4: 配置与 Compose 接线 ✅

**Files:**
- Modify: `.env.example`, `compose.yaml`, `src/jobflow/api/dependencies.py`
- Test: `tests/ops/test_wechat_configuration.py`

- [ ] Step 1: 写测试确认默认关闭微信时配置读取不触网且不影响 Telegram。
- [ ] Step 2: 运行 `python -m pytest tests/ops/test_wechat_configuration.py -q`，确认失败。
- [ ] Step 3: 增加五个空占位变量，并仅将变量传入 API 容器；禁止打印值。
- [ ] Step 4: 重新运行测试及 `python -m pytest tests/ops/test_proxy_deployment_files.py -q`。

## Task 5: 每日脚本并行编排 ✅

**Files:**
- Modify: `ops/daily_update.sh`
- Test: `tests/ops/test_daily_update_script.py`

- [ ] Step 1: 写 Shell 契约测试，验证两个发送进程并行启动、分别捕获退出码、一个失败不阻止另一个、最终退出码正确。
- [ ] Step 2: 运行 `python -m pytest tests/ops/test_daily_update_script.py -q`，确认失败。
- [ ] Step 3: 增加文章包生成调用；用后台任务和 `wait` 并行调用 Telegram/微信，并保留每个渠道状态查询逻辑。
- [ ] Step 4: 重新运行脚本测试，预期通过；再运行 `bash -n ops/daily_update.sh`。
- [ ] Step 5: 运行完整离线回归：`python -m pytest -q`。

## Task 6: README、教程与交接文档 ✅

**Files:**
- Modify: `README.md`, `README.zh-CN.md`, `docs/project-handoff.md`
- Create: `docs/wechat-test-account.md`
- Test: `tests/docs/test_public_assets.py`

- [ ] Step 1: 在 README 增加微信能力简介、默认关闭说明、安全边界和教程链接，不放真实配置示例。
- [ ] Step 2: 在教程中写测试号申请、模板字段、`.env` 变量名、人工验收和故障处理步骤，所有值使用占位符。
- [ ] Step 3: 更新交接文档，注明“测试号自动摘要 + 正式订阅号人工发布”的当前状态及 Ubuntu 联调由用户执行。
- [ ] Step 4: 运行 `python -m pytest tests/docs/test_public_assets.py -q`，并执行敏感字段扫描。

## Task 7: 集成验收与提交

**Files:**
- Modify only files listed above。
- Test: full test suite and public-secret scan。

- [ ] Step 1: 运行 `python -m pytest -q`，预期所有离线测试通过。
- [ ] Step 2: 运行 `git diff --check`、`git status --short` 和公开仓库秘密扫描，确认无真实凭据。
- [ ] Step 3: 使用虚构聚合数据生成文章包，校验四个文件可重复生成且 HTML 无脚本。
- [ ] Step 4: 记录测试用例和服务器联调待办，不执行 Ubuntu 命令。
- [ ] Step 5: 等待用户明确授权后再创建提交；未经授权不得 push。

## Task 8: 全项目链路注释与知识卡片

**Files:**
- Modify: `src/jobflow/adapters`, `src/jobflow/collectors`, `src/jobflow/models`, `src/jobflow/db`, `src/jobflow/workers`, `src/jobflow/reports`, `src/jobflow/ai`, `src/jobflow/api`, `src/jobflow/channels`, `src/jobflow/cli.py`, `src/jobflow/snapshot_backfill.py`, `ops/daily_update.sh`
- Modify: `docs/architecture.md`, `docs/learning-notes.md`, `docs/project-handoff.md`
- Modify: `D:\Altria_note\Altria的知识库\JobFlow\JobFlow 项目总览.md`, `JobFlow 项目架构与演进设计.md`

- [ ] Step 1: 为每个 Python 模块补充模块职责、上游输入、下游输出和失败边界说明。
- [ ] Step 2: 为公开函数和关键私有函数补充中文 docstring，说明参数、返回值、事务或幂等原因；不改业务逻辑。
- [ ] Step 3: 在 `docs/architecture.md` 增加端到端链路图：采集 → Adapter → ETL → PostgreSQL → FastAPI → 报告 → Telegram/微信。
- [ ] Step 4: 为每个入口补充注释：CLI、FastAPI `create_app`、报告路由、每日 Shell、快照回填入口。
- [ ] Step 5: 每层运行对应测试和 `git diff --check`，确认注释变更不改变行为。
- [ ] Step 6: 将已完成的解释同步到项目学习文档和 Obsidian 卡片，保留真实配置脱敏边界。

## Self-Review Checklist

- [ ] 覆盖 PRD 的配置、并行渠道、状态机、文章包、幂等、错误分类和安全要求。
- [ ] 计划中没有未完成占位词或未定义接口名称。
- [ ] 后续任务使用的函数、状态名和文件路径与前置任务一致。
- [ ] README 与详细教程边界符合最终决策：README 介绍功能，教程通过链接访问。
- [ ] 正式公众号自动发布明确留到未来单独设计。
