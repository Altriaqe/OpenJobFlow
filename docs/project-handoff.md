# JobFlow 项目当前状态与开发交接

更新日期：2026-08-17

这份文档是上下文压缩、新对话、换电脑或暂停开发后的第一入口。继续开发前先读取本文件，再用代码、测试、Git 和服务器实际输出确认可能变化的状态。

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
└─ channels/    Telegram 发送适配器（企业微信适配器保留但未启用）

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

详细环境、SCP、权限、代理、日志、停机和防火墙步骤见 [`ubuntu-deployment.md`](ubuntu-deployment.md)。

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
Windows 当前未提交：README.md、docs/architecture.md、docs/project-handoff.md、docs/ubuntu-deployment.md 的 V1.2 真实验收更新
Ubuntu：main 与 origin/main 在 eefad84，工作区同步时干净
Ubuntu：服务器手工脚本已另存到项目外备份后，使用仓库内可执行版本
排除：.env、真实数据、Chrome Profile、Cookie、订阅、VNC 凭据和个人知识库
```

上述 Ubuntu Git 状态来自 2026-08-17 迁移前的实际输出；之后仍可能变化。服务器另有 `/etc/systemd/system/` 单元、私有 `.env`、`/etc/jobflow-mihomo` 和项目外脚本备份。

Git 状态和服务器提交会变化。新对话开始后必须重新执行 `git status --short --branch` 和 `git log -5 --oneline`，不要只相信本文快照。

2026-08-19 最新补充：

```text
JobFlow Windows：main / origin/main = 8c5f413
JobFlow Windows 未提交：README.md、docs/architecture.md、docs/project-handoff.md、docs/ubuntu-deployment.md、.superpowers/
scraper 最新上游与 Ubuntu HEAD：2bc40f5
scraper 新版本机分支：codex/fix-chrome151-foreground-target
scraper 修复提交：7020397，已推送到个人 Fork
scraper 上游 PR：https://github.com/eatmoreduck/boss-zhipin-scraper/pull/68（Open，尚未合并）
scraper 新版工作区未提交：仅 local-output/（真实抓取产物，不得提交）
scraper Ubuntu：master 基线 2bc40f5，生产脚本已应用未提交兼容补丁
禁止提交：真实抓取 JSON、local-output/、Cookie、Profile、Token、订阅和 .env
```

## 9. 下一步

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

## 11. 新对话交接提示词

新建对话时可以发送：

```text
这是 JobFlow 项目，请先完整阅读 <LOCAL_JOBFLOW_DIR>/docs/project-handoff.md，
再读取 README.md、docs/ubuntu-deployment.md、git status 和最近 5 个提交。
个人知识库路径只在本机私有维护文档中记录，不进入公开仓库。
请以代码、测试和 Git 为正式事实来源，不要把计划写成已完成。
我是初学者，指导时说明目标、步骤、结果、为什么这样做和知识点；
如果我的表达不符合业务术语，请转换为规范业务语句后理解。
当前 V1.1 五分钟自动抓取、ETL 和 Telegram 已真实验收；
V1.2 Compose 可选服务器代理也已在 Ubuntu 完成真实报告和重启复验；
V1.3 四城市三页、每日对比简报、城市构成 PNG 和 Telegram 图文发送已完成一次真实验收；
下一步观察正式 timer 的连续运行，再独立验收整机重启恢复。
一次只推进一个可以独立验收的小步骤，不自动 commit 或 push。
```

## 12. 每次结束前维护清单

1. 更新本文件的完成度、验证结果、Git 停点和下一步；
2. 启动或部署变化同步更新 `ubuntu-deployment.md`；
3. 架构边界变化同步更新 `architecture.md`；
4. 把已完成的学习结果同步到 Obsidian，不提前创建未来 Day；
5. 运行测试、Ruff、链接和敏感信息检查；
6. 只有用户明确要求时才 commit 或 push。
