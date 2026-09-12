# JobFlow 项目当前状态与开发交接

更新日期：2026-09-10

这份文档是上下文压缩、新对话、换电脑或暂停开发后的第一入口。继续开发前先读取本文件，再用代码、测试、Git 和服务器实际输出确认可能变化的状态。

## 0. 2026-09-05 历史验收基线（V1.3.5）

以下内容是 2026-09-05 以前的历史验收基线；当前状态以本文件后面的 2026-09-10 停点为准。

V1.3.5 已把“服务器生成文章包、Windows 下载、人工导入”升级为“服务器生成文章包、自动创建正式公众号草稿、人工审核发布”。Telegram 仍按原链路自动发送，Windows 下载工具保留为故障兜底，V1.3.2 测试号接口保留供手动回归。

当前代码与 Git 停点（本次文档更新前基线）为：

```text
仓库：Altriaqe/OpenJobFlow
本机目录：<LOCAL_JOBFLOW_DIR>
稳定分支 main / origin/main：cc18655（本次 2026-09-05 文档同步前基线）
最新提交：记录双渠道稳定发送状态
离线回归：349 passed，1 skipped，1 warning
Ruff check：通过
Ubuntu 项目目录：<JOBFLOW_DIR>
Ubuntu：V1.3.5 正式公众号草稿链路已真实验收，具体 Git ref 继续前需现场复查
```

正式公众号 AppID/AppSecret 已保存在服务器私有 `.env`，API IP 白名单已配置。`api.weixin.qq.com` 通过 `JOBFLOW_NO_PROXY` 直连，Telegram 继续使用 Mihomo，两个渠道互不改路。Access Token、`draft/count`、封面永久素材、正文趋势图和 `draft/add` 均已真实成功；中文 UTF-8、内联排版和带属性 `<h1>` 标题解析已由用户在公众号后台确认满意。

文章包仍包含 `article.md`、动态中文导入 Markdown、`article.html`、`cover.png`、`trend.png` 和 `manifest.json`。正式链路现在直接读取并校验文章包，上传两类素材后创建待审核草稿。JobFlow 不自动正式发布，不自动重试失败或不确定请求；错误文章仍由维护者在正确公众号后台人工确认和删除。

正式 PRD 和实施计划为：

```text
docs/development/specs/2026-08-26-wechat-official-daily-delivery-design.md
docs/development/plans/2026-08-26-wechat-official-daily-delivery.md
```

当前已经确认：

- 个人主体，先用微信公众平台测试号验证；
- 测试号自动发送聚合摘要；
- 自动生成完整公众号文章排版包；
- 正式个人订阅号首版人工确认发布；
- Telegram 保留，与微信独立发送；
- 只公开聚合指标和趋势图；
- 结果不确定时禁止自动重发；
- 真实 appsecret、openid 和模板 ID 不写入 Git。
- V1.3.2 已覆盖微信渠道适配器、模板字段、公众号文章包、Migration 009、独立状态机、FastAPI 发送/状态/补发接口，以及 Telegram/微信并行 Shell 编排；
- `WECHAT_ENABLED=true` 已进入服务器私有配置，手动发送与手机实收通过；
- `daily_update.sh` 会并行调用 Telegram 与微信，并等待两个渠道各自结束；
- 历史文章包因 `tempfile.mkdtemp()` 默认 `0700` 导致宿主机需 `sudo` 读取，修复已通过 PR #1 合并并部署；
- 权限修复分支回归为 `306 passed, 1 skipped`，文档整理后的非 integration 回归为 `308 passed, 1 skipped`，Ruff 通过；
- Ubuntu 已验证文章目录 `0755`、文件 `0644`，普通用户无需 `sudo` 可读取；
- 正式 timer 的实时 `enabled/active/next` 已采集，Telegram 与微信公众号正式定时首轮均已实收；
- `docs/` 已按 `guides`、`reference`、`development`、`operations`、`archive` 重新分类并合并到 `main`。
- V1.3.3 公众号岗位卡片改用明文原始地址，避免个人公众号保存草稿时清除外部超链接；
- 真实 `2026-08-27` 公告包含 247 个新增岗位，正式个人订阅号首篇文章已发布；
- `downloads/` 保存真实发布产物，已加入 `.gitignore`，不得进入公共仓库。
- V1.3.4 `download-wechat-article.cmd/.ps1` 已兼容 CMD 与 Windows PowerShell 5，一次 SCP 下载后校验 `report_date`、`new_job_count` 和六个文件；目标目录存在时拒绝覆盖；
- 每台电脑使用自己的环境变量或命令参数，脚本不包含个人用户名、服务器地址、远程路径或密码；
- 2026-08-28 真实脚本验收输出新增岗位 256、正确中文文件名、建议标题和作者；公开文档测试 12 项与脚本保护测试通过。
- V1.3.5 增加 Migration 010、`/wechat/draft/create`、`/wechat/draft/status`、素材上传和按日期幂等状态；
- 永久封面以 `media_id` 验收，正文图片以 `url` 验收，避免混用接口响应契约；
- 草稿 JSON 以 `ensure_ascii=False` 编码为 UTF-8，正文使用微信可保留的内联样式，标题正则允许 `<h1>` 属性；
- 离线非 PostgreSQL 回归为 `349 passed, 1 skipped, 1 warning`，`ruff check src tests`、触及文件格式检查和 `git diff --check` 均通过；本机未加载数据库变量时不把 integration 测试记作通过。

2026-08-31 的正式 timer 运行中，ETL 与微信草稿生成成功。Telegram 首次返回 `text_uncertain`，用户在目标聊天中确认文字可见后，按受保护的 `recover-photo?confirm_text_visible=true` 流程仅补发一张热力图，未重发文字。该次运行最终完成，但仍属于一次稳定性观察样本。周趋势只在周日生成，周一不显示属于当前设计行为。

2026-09-04 已由维护者确认：微信公众号链路正常创建草稿并完成正式发表；Telegram 文字与图片链路均稳定发送。2026-09-05 因服务器断电后重启，维护者手动恢复双线路并确认正常推送。该结果计入 V1.3.5 双渠道连续稳定性观察。当前仍不把单日成功或一次手动恢复表述为公网生产级高可用完成，后续继续观察每日 timer、BOSS 登录态、图片回执、周趋势和重复投递防护。

下一步是继续观察正式 timer 的连续运行，并在每周结束时验收本周与上周对比。公众号最终审核与发布保持人工确认。自动备份恢复、登录失效通知和公网 HTTPS 仍未完成。

## 2026-09-07 React 运营控制台与只读 API 停点

React + Vite + TypeScript 前端已加入 `frontend/`，定位为独立的运营控制台。当前包含平台总览、运行中心、投放中心、分析指标和告警记录五个可点击页面，分析页会尝试读取 `GET /analytics/cities`，服务不可用时保留演示数据并标记未连接。投放按钮仍禁用，未接入真实投放动作。

FastAPI 增加本地前端 CORS 白名单，默认允许 `localhost:5173` 与 `127.0.0.1:5173`；数据库连接创建失败统一返回 `503`，不把配置细节暴露给客户端。项目使用本地 Python 3.12.13 环境验证，健康与分析 API 测试共 18 项通过，前端 `npm run build` 通过。

本次公开代码提交为 `57e695a`，已推送到 `origin/main`。该提交不包含之前暂存的 Streamlit 文件；当前 Streamlit 修改仍需单独处理。React 依赖目录已加入 `.gitignore`，凭据和真实环境变量未进入仓库。

当前状态是“React/API 代码已推送，数据库与 Ubuntu 服务器现场部署待验收”，不能表述为服务器已经运行新前端。下一步应先在服务器复查 Git、镜像和数据库，再决定采用静态前端服务或反向代理挂载；投放接口必须在只读状态稳定后单独设计确认流程。

相关计划：

```text
docs/development/plans/2026-09-06-react-operations-console.md
```

## 2026-09-10 Streamlit 运营控制台服务器停点

第一阶段 Streamlit 控制台现已通过 Docker Compose 在 Ubuntu 服务器启动，并通过本机 SSH 隧道访问。控制台包含平台总览、运行中心和投放中心；阶段定义位于 `config/platform_stages.yaml`，运行检查和日期/渠道投放记录使用 Migration 011 的 PostgreSQL 表。管理员 Token 只从服务器私有环境读取；Telegram 与微信公众号始终是独立动作，微信公众号只创建草稿，人工审核后发布。

本地 `main` 与 `origin/main` 当前均为 `9aff50a`。本轮与控制台有关的已推送提交为：

```text
940af70 增加按日期渠道投放状态服务
a18681e 增加按日期投放工作台接口
51acf99 接入按日期渠道投放工作台
6183334 补充投放工作台部署验收
eaedb7e 修正 Dashboard 容器内 API 地址
bb32f31 修正工作台查询参数名
49ea0a8 修正 Dashboard 数据库容器地址
9aff50a 确保 Dashboard 等待 API 就绪
```

已现场确认的部署事实：

- Dashboard 容器绑定服务器回环地址的 `8502`，本地通过 SSH 隧道打开页面；
- Dashboard 已成功连接 PostgreSQL；此前错误使用容器内 `127.0.0.1:5432`，现固定为 `postgres:5432`；
- Dashboard 调用 API 使用 Compose 服务地址 `http://api:8000`，并等待 API 健康检查通过后启动；
- 运行中心页面已可打开，最近一次页面显示的 `wechat`、`telegram`、`latest_etl`、`boss_login`、`ready` 等检查均为 `succeeded`；
- 本地相关 Dashboard/operations 测试为 `24 passed`；此前工作台、API、微信相关测试为 `57 passed`，完整离线回归为 `385 passed, 1 skipped`。PostgreSQL 集成测试仍依赖本机私有数据库环境，未把环境缺失记为通过。

2026-09-10 本轮只读复查已完成：服务器 `HEAD=9aff50a`，`api` 与 `postgres` 为 healthy，`dashboard` 正常运行并绑定 `127.0.0.1:8502`；Dashboard 容器输出 `postgres:5432 http://api:8000`，`/ready` 返回 `ready`。`GET /dashboard/workbench` 对 2026-09-09 和 2026-09-10 均返回快照、文章可用，Telegram 为 `sent`、微信为 `created`，两个渠道都没有可执行动作。本轮没有调用 Telegram 或微信写接口。

服务器工作区不是干净状态，存在未提交的 `ops/manual_capture_worker.sh` 修改；在确认该服务器本地修改的来源和用途前，不要执行会覆盖它的 Git 操作。上述检查只证明本次只读状态，不替代后续 timer 连续运行和整机恢复验收。

服务器继续操作只使用 Compose Dashboard 服务，不重启 API、PostgreSQL、daily timer 或 BOSS Chrome：

```bash
cd <JOBFLOW_DIR>
git pull --ff-only
DASHBOARD_PORT=8502 docker compose -f compose.yaml -f compose.proxy.yaml \
  --profile dashboard up -d --no-build --force-recreate dashboard
docker compose -f compose.yaml -f compose.proxy.yaml ps api dashboard postgres
docker compose -f compose.yaml -f compose.proxy.yaml \
  exec dashboard sh -lc 'echo "$POSTGRES_HOST:$POSTGRES_PORT $JOBFLOW_API_BASE"'
```

期望 Dashboard 容器输出仅包含：`postgres:5432 http://api:8000`。本地 Windows PowerShell 单独保持隧道：

```powershell
ssh -N -L 8502:127.0.0.1:8502 <SSH_USER>@<TAILSCALE_IP>
```

浏览器入口为 `http://127.0.0.1:8502`。`ssh -L` 必须在 Windows 本机运行，不能在 Ubuntu 服务器终端运行；端口已占用时先检查现有隧道，不随意结束进程。

设计与实施计划：

```text
docs/development/specs/2026-09-05-platform-operations-dashboard-design.md
docs/development/plans/2026-09-05-platform-operations-dashboard.md
```

新对话恢复提示词：

```text
继续 OpenJobFlow 运营控制台和 V1.3.5 微信公众号自动草稿维护。
项目路径：<LOCAL_JOBFLOW_DIR>
请先阅读 docs/project-handoff.md、
docs/guides/wechat-official-draft.md
和 docs/reference/architecture.md，
然后检查 git status --short --branch 与 git log -5 --oneline。
先读取本文件中“2026-09-10 Streamlit 运营控制台服务器停点”。
本地和服务器 HEAD 已到 9aff50a；服务器 Dashboard、数据库/API 地址、API 就绪状态和 2026-09-09/10 工作台只读查询均已验收。
服务器仍有未提交的 ops/manual_capture_worker.sh 修改；下一步先只读确认该差异的来源和用途，不要覆盖，不要调用 Telegram 或微信写接口。
正式公众号自动草稿已真实验收，微信公众号保持自动创建草稿、人工审核发布；继续前复查 API 状态和 timer。
真实 AppID、AppSecret、Token、素材 ID、服务器地址和真实文章包不得写入 Git。
```

## 1. 项目目标

JobFlow 第一版目标是部署在个人 Ubuntu 服务器上的轻量 AI 数据中台：

```text
Ubuntu Chrome CDP / 手工快照采集招聘数据
→ JobFlow ETL 清洗、标准化、去重和入库
→ PostgreSQL 分层保存与聚合
→ FastAPI 提供固定只读指标
→ OpenAI 模型生成事实约束报告
→ Telegram Bot 私聊发送
```

长期可以扩展其他数据源、指标和机器人渠道，但第一版不引入复杂分布式架构。

## 2. 当前完成度

### 已实现并真实验收

- BOSS 本地快照读取、验证、薪资解析和技能清洗；
- `ops/raw/core/mart` PostgreSQL 分层与 5 个 migration；
- 幂等 Upsert、批次状态、事务提交和失败回滚；
- 城市岗位、城市月薪和热门技能三个 mart View；
- 三个 FastAPI 分析接口、`/health`、`/ready`、`/docs`；
- Dockerfile 与 `postgres/migrate/etl/api` Compose 编排；
- Ubuntu 22.04 局域网部署；
- OpenAI 报告、Telegram 直发和受 Bearer Token 保护的完整报告接口；
- `query` 固定规则简报与可选 `ai` 模式；
- Ubuntu Chrome 151、Xvfb、CDP 和 BOSS 人工登录态；
- 上海、北京、杭州、深圳各 15 条的真实抓取、合并、Adapter 和 ETL；
- `ops/daily_update.sh` 的任务锁、登录预检查、原子快照、ETL 和 Telegram 编排；
- Xvfb 与 Chrome systemd 长期服务；
- 每天 `09:00 Asia/Shanghai` 的 systemd timer；
- 5 分钟 transient timer 真实触发：ETL 完成、报告返回 `city_count=4`、Telegram 手机私聊真实收到中文报告。
- Ubuntu Mihomo 代理：独立容器方案和 V1.2 Compose 接管方案均完成 `getMe`、真实 `mode=query` 报告与容器重启后外联验收。

### V1.2 已实现并完成 Ubuntu 真实部署验收

- `compose.proxy.yaml` 可选 Mihomo 覆盖；
- `deploy/mihomo/config.example.yaml` 安全订阅占位模板；
- `runtime/` Git 忽略和 `MIHOMO_CONFIG_DIR` 配置接口；
- 默认直连与代理覆盖两种 Compose 配置均已在本机通过解析；
- 代理部署契约测试已通过；
- Ubuntu 已同步到 `eefad84`，`ops/daily_update.sh` 保持可执行并通过 `bash -n`；
- 私有配置继续保存在 `/etc/jobflow-mihomo`，通过 `MIHOMO_CONFIG_DIR` 挂载，不进入 Git；
- 原独立容器已停止并改名为 `jobflow-mihomo-pre-v1.2` 作为临时回退备份；
- 当前代理由 Compose 服务 `mihomo` 管理，容器为 `jobflow-mihomo-1`，`restart=unless-stopped`，无宿主机端口绑定；
- API 实际环境为 `HTTP_PROXY/HTTPS_PROXY=http://mihomo:7890`，已通过 `getMe`、真实 `mode=query` 报告、手机私聊收件和 Mihomo 重启后复验。

### V1.3 已完成一次 Ubuntu 真实端到端验收

- JobFlow 代码已包含每日不可变快照、日环比、周末周对比、城市构成 PNG 和 Telegram 图文发送；
- `boss-zhipin-scraper` 上游基线为 `2bc40f5`，列表链路使用 CDP Network 域被动捕获；
- Ubuntu Chrome 151 中，后台 Target 无法稳定取得搜索响应；Issue #67 已创建；
- 临时兼容修复只让 `check_login_state`、`scrape_list`、`run_smoke_test` 使用 `background=False`，保留 helper 默认后台、visibility override、焦点仿真和详情后台边界；
- 本机新版分支 `codex/fix-chrome151-foreground-target` 通过抓取器 86 个测试、全仓库 99 个测试、语法和差异检查；
- Ubuntu `--check`、`--smoke-test` 和两页真实抓取依次通过；两页抓取获得 30 条真实岗位与明文薪资；
- 正式 `daily_update.sh` 完成上海、北京、杭州、深圳各 3 页和 45 条，共合并 180 条；
- ETL 输出 `completed`，日报投递状态为 `sent`，Telegram 真实收到中文文字与城市构成 PNG，脚本退出码为 0；
- 城市图表示固定页数抓取样本构成，不代表全市场岗位份额。本轮四城都抓满 45 条，因此各为 25%。

当前边界：scraper 服务器工作区应用的是基于 `2bc40f5` 的未提交补丁；本机修复已提交为 `7020397`，推送到个人 Fork，并向上游创建 PR `#68`，但尚未合并。旧版 `26b272f` 修复分支和旧补丁仅保留作历史，不得部署。

### 已部署并完成服务器代理定时推送验收

- 2026-08-17 正式 09:00 timer 已触发，抓取和 ETL 成功；Telegram 因当时依赖的 Windows 代理已关闭而返回 HTTP 502；
- 同日先用项目外独立 Mihomo 恢复 Telegram，随后迁移为 V1.2 Compose 管理的 `mihomo` 服务并完成真实报告送达；
- 2026-08-18 Windows 本地机关机时，Ubuntu 已通过 Compose `mihomo` 完成正式定时推送并送达 Telegram；
- 仍待验收或实现：连续多日自动运行、Ubuntu 或 Chrome 重启后的登录恢复流程、BOSS 登录失效自动通知。

### 尚未实现

- 多关键词采集和更大抓取范围（V1.3 当前固定为四城市、每城三页、单一关键词）；
- 合规动态数据源或正式授权边界；
- API 只读数据库角色；
- Streamlit；
- 公网域名、Caddy、HTTPS、完整鉴权和限流；
- PostgreSQL 自动备份、恢复演练、监控与告警。

## 3. 代码结构

```text
src/jobflow/
├─ adapters/    数据源读取、校验和标准化
├─ collectors/  HTTP 请求边界
├─ models/      统一 JobRecord
├─ db/          PostgreSQL 连接、写入、批次和分析查询
├─ workers/     ETL 与事务编排
├─ api/         FastAPI 健康、分析和报告路由
├─ ai/          OpenAI 报告生成
├─ reports/     查询、总结、发送的业务编排
└─ channels/    Telegram、企业微信和微信公众号发送适配器

migrations/     001 到 005 的 PostgreSQL migration
tests/          单元测试与真实 PostgreSQL 集成测试
ops/            Ubuntu 每日抓取、ETL 和 Telegram 编排脚本
compose.yaml    PostgreSQL、migration、ETL、API 编排
Dockerfile      Python 3.12 应用镜像
```

## 4. 当前接口

| 方法 | 路径 | 状态 | 说明 |
| --- | --- | --- | --- |
| GET | `/health` | 已验收 | API 进程存活 |
| GET | `/ready` | 已验收 | PostgreSQL 就绪 |
| GET | `/analytics/cities` | 已验收 | 城市岗位数量 |
| GET | `/analytics/salaries/cities` | 已验收 | 城市月薪统计 |
| GET | `/analytics/skills` | 已验收 | 热门技能 |
| POST | `/reports/cities/send` | 已真实验收 | 默认 query 固定简报；`mode=ai` 才调用 OpenAI 模型；最终发送 Telegram 私聊 |
| POST | `/reports/daily/multi/wechat/article/generate` | 已真实验收 | 从完整四关键词快照生成公众号文章包，不发送 Telegram |
| GET | `/reports/daily/multi/wechat/article/status` | 已实现 | 返回脱敏文章包状态，不暴露文件路径或凭据 |
| GET | `/docs` | 已验收 | Swagger UI |
| GET | `/openapi.json` | 已实现 | OpenAPI 规范 |

分析接口的 `limit` 默认 20，范围 1 到 100。报告接口需要 `Authorization: Bearer <REPORT_TRIGGER_TOKEN>`。

## 5. Windows 开发环境启动

项目路径：

```text
<LOCAL_JOBFLOW_DIR>
```

基础检查：

```cmd
cd /d <LOCAL_JOBFLOW_DIR>
conda activate jobflow
python --version
pytest -q
ruff check .
ruff format --check .
```

Python 代码通过 `os.getenv()` 读取 PostgreSQL 和外部服务配置，不会自动解析 `.env`。在 Windows 直接运行 Uvicorn 或集成测试前，必须确保当前终端进程已经加载所需环境变量；不要把真实值写进文档。

本地启动 API：

```cmd
uvicorn jobflow.api.app:app --reload --host 127.0.0.1 --port 8000
```

本地验证：

```cmd
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/ready"
curl "http://127.0.0.1:8000/analytics/cities?limit=3"
```

进程启动不等于数据库已经就绪；必须同时检查 `/ready` 和真实分析接口。

## 6. Ubuntu 第一版启动

```text
服务器：Ubuntu 22.04.5 LTS
用户：<SSH_USER>
IP：<SERVER_IP>
项目：<JOBFLOW_DIR>
```

标准运行：

```bash
ssh <SSH_USER>@<SERVER_IP>
cd <JOBFLOW_DIR>
docker compose up -d postgres
docker compose run --rm migrate
docker compose run --rm etl /data/raw/inbox/boss_jobs.json
docker compose up -d api
docker compose ps
```

无新快照时：

```bash
docker compose up -d postgres api
```

详细环境、SCP、权限、代理、日志、停机和防火墙步骤见 [`ubuntu-deployment.md`](guides/ubuntu-deployment.md)。

## 7. 当前运行证据

2026-08-17 正式 09:00 timer 与代理修复：

```text
timer：按时触发
四城市抓取：完成
ETL：completed，数据库更新保留
Telegram：HTTP 502
失败边界：API 容器当时仍依赖已关机的 Windows 主机代理
daily service：status=1/FAILURE

修复后 Mihomo：独立 Docker 容器，restart=unless-stopped
代理端口：只在 JobFlow Docker 网络中使用，不发布宿主机端口
Telegram getMe：HTTP 200 / ok=true
mode=query 报告接口：status=sent
手机私聊：真实收到新报告
Mihomo 容器手动重启后：Telegram getMe 仍为 HTTP 200 / ok=true

V1.2 迁移提交：eefad84
V1.2 Compose 服务：jobflow-mihomo-1 / running
V1.2 API：running / healthy
V1.2 Mihomo restart：unless-stopped
V1.2 Mihomo port_bindings：{}
V1.2 API HTTP_PROXY/HTTPS_PROXY：http://mihomo:7890
V1.2 Telegram getMe：HTTP 200 / ok=true
V1.2 mode=query：status=sent / city_count=4
V1.2 手机私聊：真实收到中文报告
V1.2 Mihomo 重启后 getMe：HTTP 200 / ok=true
旧独立容器：jobflow-mihomo-pre-v1.2 / exited / 暂留回退
合盖策略：systemd-logind 三种 HandleLidSwitch 均为 ignore
合盖实测：1117 次 Ping / 0% 丢包，API /ready 返回 ready

2026-08-18 正式定时推送：Windows 本地机关闭
Ubuntu：持续稳定运行
服务器代理：Compose mihomo
Telegram：用户确认定时推送正常送达
链路结论：定时推送不依赖 Windows 本地机或本地代理
```

V1.2 Compose 接管、即时报告链路、单次 Mihomo 容器重启，以及 Windows 本地机关机后的服务器代理正式定时推送均已真实通过；整台 Ubuntu 重启和连续多日稳定性仍需独立观察。2026-08-18 的定时送达由用户实际收件确认；本文不虚构未提供的批次号或行数。个人订阅、节点和服务器私有代理配置不属于公开仓库。

2026-08-16 五分钟 transient timer：

```text
daily_update.sh：code=exited / status=0/SUCCESS
ETL：completed
Telegram API：Telegram report sent / city_count=4
手机私聊：真实收到中文查询简报
报告岗位总量：397
上海：124
北京：92
杭州：91
深圳：90
正式 timer：enabled / active (waiting)
正式下一次触发：2026-08-17 09:00:00 CST
```

本次 transient 运行后尚未补做最新 `ops.batches` 和 `raw.job_records` SQL 查询；不能根据旧批次查询伪造最新 batch id 或 row_count。ETL 完成证据来自 systemd journal，报告数据来自 Telegram 实际消息。

本轮最新本机验证：

```text
ops 定向测试：8 passed
非 PostgreSQL 回归：118 passed，1 warning
Ruff check / format：通过
默认 Compose / 代理覆盖 Compose：解析通过
Ubuntu 正式脚本：可执行，bash -n 通过
```

本机未运行 PostgreSQL 容器，因此本轮没有重跑数据库集成测试；Ubuntu 之前的 ETL、PostgreSQL 和本次 V1.2 外部服务验收仍是独立证据。

## 8. Git 与部署停点

2026-08-17 检查时：

```text
Windows：main 与 origin/main 在 eefad84，工作区在本轮文档维护前干净
Windows 当前未提交：README.md、docs/reference/architecture.md、docs/project-handoff.md、docs/guides/ubuntu-deployment.md 的 V1.2 真实验收更新
Ubuntu：main 与 origin/main 在 eefad84，工作区同步时干净
Ubuntu：服务器手工脚本已另存到项目外备份后，使用仓库内可执行版本
排除：.env、真实数据、Chrome Profile、Cookie、订阅、VNC 凭据和个人知识库
```

上述 Ubuntu Git 状态来自 2026-08-17 迁移前的实际输出；之后仍可能变化。服务器另有 `/etc/systemd/system/` 单元、私有 `.env`、`/etc/jobflow-mihomo` 和项目外脚本备份。

Git 状态和服务器提交会变化。新对话开始后必须重新执行 `git status --short --branch` 和 `git log -5 --oneline`，不要只相信本文快照。

2026-08-19 最新补充：

```text
JobFlow Windows：main / origin/main = 8c5f413
JobFlow Windows 未提交：README.md、docs/reference/architecture.md、docs/project-handoff.md、docs/guides/ubuntu-deployment.md、.superpowers/
scraper 最新上游与 Ubuntu HEAD：2bc40f5
scraper 新版本机分支：codex/fix-chrome151-foreground-target
scraper 修复提交：7020397，已推送到个人 Fork
scraper 上游 PR：https://github.com/eatmoreduck/boss-zhipin-scraper/pull/68（Open，尚未合并）
scraper 新版工作区未提交：仅 local-output/（真实抓取产物，不得提交）
scraper Ubuntu：master 基线 2bc40f5，生产脚本已应用未提交兼容补丁
禁止提交：真实抓取 JSON、local-output/、Cookie、Profile、Token、订阅和 .env
```

## 2026-09-08 React 正式操作链路与手动抓取桥接停点

```text
最新代码：4959843 修复 Telegram 状态查询字段歧义
公开仓库：<LOCAL_JOBFLOW_DIR>
服务器目录：<JOBFLOW_DIR>
```

React + Vite + TypeScript 运营控制台已经接入管理员会话、HttpOnly Cookie、二次确认和真实操作状态。服务器检查、Telegram 投放和微信公众号草稿入口均由 FastAPI 受保护接口承接，前端不保存报告 Token，也不直接调用外部渠道。前端构建、相关后端测试、Ruff 和 `git diff --check` 已通过；当前仍属于开发/上线演进，README 暂不更新。

手动投放的服务端规则如下：过去日期有快照则直接复用，没有快照则拒绝；今天有快照则直接投放，没有快照则请求宿主机抓取并完成 ETL，成功后才继续投放；未来日期拒绝；已投放返回 `already_sent`，不重复调用 Telegram。前端日期控件只是体验层限制，不能替代服务端判断。

API 容器与宿主机抓取器通过共享目录桥接：

```text
runtime/manual-capture/YYYY-MM-DD.request
→ jobflow-manual-capture-worker.service
→ JOBFLOW_CAPTURE_ONLY=true ops/daily_update.sh
→ YYYY-MM-DD.result
→ API 读取 succeeded 后继续投放
```

队列目录由 `JOBFLOW_CAPTURE_QUEUE` 配置，等待时长由 `JOBFLOW_CAPTURE_TIMEOUT` 配置。服务器 worker 已因 runtime 权限问题修复为 `altria` 可写并显示 active；这只证明 worker 进程正在运行，不等于“无快照到抓取、ETL、Telegram 投放”完整链路已验收。

Telegram 曾出现“投放接口 200、状态查询 503”的分离故障：投放记录在 `ops.report_deliveries`，微信草稿记录在 `ops.report_channel_deliveries`，旧查询读错表且 SQL 字段有歧义。现已修复状态查询，但仍需分别核对接口响应、数据库状态和手机端实际收件。

部署边界：本机已确认 `main` 与 `origin/main` 指向 `4959843`；服务器是否已拉取该提交需通过 SSH 现场确认。整机重启自动恢复、连续无人值守、公网高可用和今天无快照完整实跑仍未验收。公开文档不记录 Token、密码、Webhook、Cookie、Chat ID、真实服务器地址或私钥。

## 2026-09-09 微信公众号草稿排障暂停交接

本节是当前最高优先级停点。它是一次运行排障记录，不是版本更新；React 可视化和运营控制台仍处于开发/上线演进，README 暂不更新，也不新增版本号或每日记录。

### 已确认的 2026-09-09 运行结果

以下结果来自服务器任务日志、文章包和受控接口诊断，必须与更早的“微信公众号草稿已验收”历史记录区分：

- BOSS 抓取成功；四关键词 ETL 成功；任务日志记录合并数据 180 条；
- 微信文章包生成成功，包含 `article.html`、`article.md`、`cover.png`、`trend.png` 和 `manifest.json`；`manifest.json` 的 `new_job_count` 为 268。该字段与日志中的合并样本数属于不同记录口径，后续不要互相替换；
- Telegram 本次状态为 `sent`，不要因为微信失败而重新投放 Telegram；
- 微信草稿创建失败，systemd 最终失败边界在微信草稿阶段；ETL、文章包和 Telegram 不因该失败回滚；
- 文章包真实路径为 `runtime/reports/2026-09-09/wechat/`。此前一次“图片缺失”判断漏写了 `wechat/` 子目录，属于诊断路径错误，不是微信拒绝。

### 已完成的受控诊断

- API 容器的 `runtime` 权限曾错误，出现 `PermissionError`；已按容器运行 UID/GID 修复目录属主和读写权限，之后文章包成功生成；
- 正式账号环境变量存在；Token 请求返回 HTTP 200、无微信错误码且取得 Token；
- 趋势图临时素材上传返回 HTTP 200；封面永久素材上传返回 HTTP 200，均未返回微信错误码；
- 尚未取得本次 `draft/add` 的成功响应。用户在最终草稿受控验证前暂停，因此不能写成“草稿已创建”，也不能直接重试。

### 版本和诊断边界

服务器容器内当前实际暴露的 `jobflow.channels.wechat_draft` 函数包括 `get_wechat_access_token`、`upload_image`、`build_draft_payload` 和 `create_draft`，没有 `_load_package`。这说明服务器运行模块与此前诊断所依据的源码版本/函数名不完全一致。下一次修改前必须先确认服务器 Git ref、API 镜像和容器内实际源码，再与 `<LOCAL_JOBFLOW_DIR>` 对比，不能凭旧函数名盲改本地代码或推送。

用户要求暂停后，本次没有继续创建草稿、重跑每日任务、重发 Telegram、重建/重启 API 或修改服务器源码；之前的 Token 和素材上传诊断已经产生了对应的微信接口请求，不能把本次过程描述为“完全只读”。

### 新对话第一步

新对话必须按以下顺序执行，每次只做一个可验收的小步骤：

```text
读取本节和 docs/guides/wechat-official-draft.md
→ 只读确认服务器 Git、API 镜像、容器、/ready 和 2026-09-09 草稿状态
→ 查看公众号后台是否已有同日草稿
→ 对照服务器实际模块与 <LOCAL_JOBFLOW_DIR> 源码
→ 明确根因后再决定最小代码修复
```

在确认数据库状态和公众号后台之前，禁止调用 `draft/add`、普通每日投放接口或完整 `daily_update.service`；禁止重复 Telegram。若发现同日草稿已存在，按幂等规则停止，不创建第二份。

详细运维记录：[`operations/2026-09-09-wechat-draft-failure-handoff.md`](operations/2026-09-09-wechat-draft-failure-handoff.md)。

## 9. 下一步

### V1.3.5 自动创建正式公众号草稿

```text
文章包生成成功
→ 上传封面永久素材并取得 media_id
→ 上传正文趋势图并取得可嵌入 url
→ 以 UTF-8 JSON 创建正式公众号草稿
→ 后台中文、内联样式、标题和图片已验收
→ Windows 一键下载脚本保留为人工兜底
→ 最终审核与发布继续由人工确认
→ 2026-09-04 微信公众号与 Telegram 双链路稳定发送，继续计入连续观察
→ 2026-09-05 服务器断电重启后手动恢复双线路，正常推送
→ 继续记录连续多日运行
→ 每周结束时验证本周与上周对比
```

### 运行观察

```text
后续继续观察 V1.3 在 V1.2 代理下的正式 timer
→ systemd journal 留存运行证据
→ 抓取、ETL 与 Telegram 结果
→ 连续多日记录
```

### 后续抓取范围扩充

V1.3 已把单一关键词的采集范围扩为上海、北京、杭州、深圳四个城市，每城三页，并完成 180 条样本的真实端到端验收。后续版本如增加多关键词或继续扩大范围，仍需逐项确认：

```text
增加哪些城市
增加哪些关键词
每城抓取多少页
是否抓取详情页
systemd 45 分钟超时是否调整
BOSS 风控和失败保护
```

V1.2 已专用于可选服务器代理；V1.3 已完成的四城市三页范围可以写入验收事实，但多关键词和更大范围不能提前写成已实现。

## 10. 已知问题与注意事项

- Ubuntu 必须使用 `docker compose`，旧 `docker-compose` 与 Docker 29 不兼容；
- Docker 下载如需代理，在 `.env` 中使用 `<PROXY_HOST>:<PROXY_PORT>`；代理端必须允许服务器访问；
- `data/raw` 和 `data/raw/inbox` 需要 `711` 目录穿越权限，不能直接放宽为 `777`；
- `.env` 权限为 `600`，不得提交或输出实际值；
- PostgreSQL `5432` 只绑定本机，API `8000` 只允许局域网；
- 当前是按需开机的个人第一版，不是公网高可用生产系统；
- Windows 本机关机不影响 Ubuntu timer；Ubuntu 必须保持开机、联网；
- Ubuntu 笔记本已配置合盖不休眠并完成网络与 `/ready` 实测；长期合盖仍必须保持供电和散热；
- Xvfb 与 Chrome 长期运行，Chrome/BOSS 重启后可能需要 VNC 人工登录；
- daily script 使用 query 固定简报，不应表述为本次真实调用 AI；
- 真实 BOSS 快照不进入 Git；
- 代码实现、离线测试、真实外部联调是三个不同完成层级。
- 现有 `docker compose run --rm migrate` 会从 001 重放全部 migration；服务器历史数据使旧 Migration 005 的薪资约束失败。本次部署已单独执行 008 恢复正确约束，再执行 009。后续应把 migration runner 改为带版本记录的增量执行，不能把本次手工顺序当作长期方案。
- V1.3.2 手动微信送达、文章包权限和正式双渠道首轮均已验收；后续仍需连续运行和故障恢复证据。
- V1.3.5 正式订阅号当前为“服务器自动生成并创建草稿、维护者人工审核发布”，不是公众号 API 自动正式发布。
- Windows `download-wechat-article.cmd/.ps1` 已真实拉取 2026-08-28 六文件文章包，校验 `new_job_count=256`，兼容 Windows PowerShell 5 中文编码；它只下载和整理，不自动发布。
- `downloads/` 和 `runtime/` 含真实岗位发布产物，只能留在本地或服务器，不得提交公共仓库。
- 微信草稿失败不回滚 ETL 或 Telegram；`failed`、`uploading` 和网络超时都应先检查后台与状态，不得自动重复创建。
- `api.weixin.qq.com` 的直连例外只作用于微信 API；Telegram 的 Mihomo 路径不得因排查微信而整体移除。

## 11. 新对话交接提示词

新建对话时可以发送：

```text
这是 OpenJobFlow 项目，请先完整阅读 <LOCAL_JOBFLOW_DIR>/docs/project-handoff.md，
再读取 docs/guides/wechat-official-draft.md、docs/reference/architecture.md、
git status 和最近 8 个提交。
个人知识库路径只在本机私有维护文档中记录，不进入公开仓库。
请以代码、测试和 Git 为正式事实来源，不要把计划写成已完成。
我是初学者，指导时说明目标、步骤、结果、为什么这样做和知识点；
如果我的表达不符合业务术语，请转换为规范业务语句后理解。
当前公开分支 main/origin/main 为 9aff50a；Streamlit Dashboard 已在 Ubuntu Compose 中可通过 SSH 隧道访问，数据库连接和运行中心检查已成功。
“2026-09-10 Streamlit 运营控制台服务器停点”的只读验收已完成；下一步先确认服务器未提交的 ops/manual_capture_worker.sh 差异，不要覆盖，也不要调用 Telegram 或微信写接口。
2026-09-09 微信草稿排障事件已由维护者确认成功发表并关闭；原始记录仅保留作安全排障证据。公众号保持自动创建草稿、人工审核发布，任何同日重试前必须先查数据库与公众号后台。
一次只推进一个可以独立验收的小步骤，不自动 commit 或 push。
```

## 12. 每次结束前维护清单

1. 更新本文件的完成度、验证结果、Git 停点和下一步；
2. 启动或部署变化同步更新 `ubuntu-deployment.md`；
3. 架构边界变化同步更新 `architecture.md`；
4. 把已完成的学习结果同步到 Obsidian，不提前创建未来 Day；
5. 运行测试、Ruff、链接和敏感信息检查；
6. 只有用户明确要求时才 commit 或 push。
