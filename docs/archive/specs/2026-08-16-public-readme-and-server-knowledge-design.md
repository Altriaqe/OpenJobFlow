# JobFlow V1.1 公开 README 与服务器知识库维护设计

**日期：** 2026-08-16

**状态：** 已经用户口头批准，已完成书面设计自检

**范围：** JobFlow V1.1 公开仓库文档、本机项目文档和个人 Obsidian 知识库

## 1. 背景

JobFlow V1.1 已完成一次真实的五分钟自动端到端验收：Ubuntu 上的定时触发器启动每日任务，任务复用 Chrome 登录态抓取四城市快照，执行 ETL 和 PostgreSQL 入库，然后生成固定规则中文简报并发送到 Telegram 私聊。

当前 README 同时承担公开介绍、部署手册、个人服务器运维和阶段交接，内容过长且个人环境信息与通用使用说明混在一起。本次维护将重新划分公开 README、仓库详细文档和个人知识库的责任。

## 2. 目标

1. 让第一次打开仓库的用户理解 JobFlow 的用途、功能边界和数据链路。
2. 让用户可以从合规 JSON 快照开始，完成 Docker Compose、migration、ETL、FastAPI 和报告调用。
3. 把 OpenAI 模型和 Telegram 明确定义为可选增强能力，不得让未配置外部服务的用户无法使用基础查询链路。
4. 为用户可配置变量和当前仍需修改文件的 DIY 项提供可查索的入口。
5. 在个人知识库中建立独立服务器维护区，记录 JobFlow 生态的真实目录、服务、容器、端口和修改入口。
6. 保留“代码实现”、“离线测试”、“单次真实验收”和“连续生产稳定”之间的边界。

## 3. 非目标

- 不实施 V1.2 的城市、关键词、页数或详情页扩容。
- 不把 BOSS 自动采集伪装成无需登录、无需授权的默认能力。
- 不向公开仓库写入个人服务器地址、SSH 用户、私有目录或个人中转服务商名称。
- 不记录密码、API Key、Bot Token、Chat ID、Cookie、Webhook、VNC 密码或 `.env` 实际值。
- 不创建 JobFlow Day 23 每日记录。

## 4. 公开使用边界

### 4.1 默认入口

公开 README 的默认入口是用户自己获得的合规 JSON 招聘快照。仓库必须让用户在不依赖个人 BOSS 登录态和独立采集项目的情况下，理解并运行下游链路。

### 4.2 高级可选入口

V1.1 的 Ubuntu Chrome/CDP 自动采集作为高级部署方式。公开文档必须说明它依赖独立采集器、用户自己的合法访问权限、人工登录和平台安全验证。文档不提供绕过验证码、风控或平台限制的方法。

### 4.3 报告模式

- `mode=query`：读取 PostgreSQL 聚合数据，使用固定规则生成中文简报，不调用 AI。
- `mode=ai`：把结构化统计结果交给 OpenAI 模型生成自然语言总结。

公开文档只使用“OpenAI 模型”或“OpenAI 兼容接口”的中性表述，不提及个人中转服务。

## 5. 文档分层

### 5.1 公开 README

README 面向第一次打开仓库的用户，按以下顺序组织：

1. 项目定位和核心能力。
2. 实现、真实验收和待长期验证的完成边界。
3. 从 JSON 快照到 Telegram 的 Mermaid 架构图。
4. 环境要求和五分钟快速启动。
5. 必填、可选和部署环境变量。
6. JSON 快照格式和 ETL 入口。
7. 分析 API、query 报告、OpenAI 报告和 Telegram 推送示例。
8. 项目目录树和每个核心文件的职责。
9. DIY 修改入口。
10. 详细部署、维护、安全和项目文档链接。

README 中所有地址、用户名、路径和凭据均使用说明性占位符。

### 5.2 仓库 `docs/`

`docs/` 保留完整的架构、Ubuntu 部署、systemd、VNC 登录恢复、数据批次检查、故障排查和上下文交接说明。README 只保留最小可运行路径，通过链接进入详细文档。

### 5.3 个人知识库

在 `JobFlow/服务器维护/` 下创建：

- `JobFlow 服务器总览.md`
- `JobFlow 服务器项目与文件地图.md`
- `JobFlow 服务、容器与端口地图.md`
- `JobFlow 修改入口与维护手册.md`

个人知识库可记录真实服务器地址、SSH 用户、项目目录和端口，但仍不得记录任何凭据实际值。

## 6. 配置与 DIY 设计

### 6.1 已环境变量化

README 和 `.env.example` 必须按用途解释：

- PostgreSQL：`POSTGRES_HOST`、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_PORT`。
- FastAPI：`API_BIND_HOST`、`API_PORT`。
- 构建和网络：`PIP_INDEX_URL`、`PIP_DEFAULT_TIMEOUT`、`JOBFLOW_HTTP_PROXY`、`JOBFLOW_HTTPS_PROXY`、`JOBFLOW_NO_PROXY`。
- OpenAI：`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`。
- Telegram：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
- 报告接口保护：`REPORT_TRIGGER_TOKEN`。

### 6.2 尚未环境变量化

城市、关键词、抓取页数、每日执行时间、数据快照路径等当前如果仍由脚本或 systemd 单元定义，文档必须标注真实修改文件，不得虚构不存在的环境变量。

## 7. 服务器维护区内容

### 7.1 JobFlow 生态范围

服务器维护区只盘点 JobFlow 相关对象：

- JobFlow 主项目。
- BOSS 数据采集项目。
- JobFlow 专用 Chrome Profile。
- Xvfb、Chrome、daily-update service 和 timer。
- PostgreSQL 和 FastAPI Compose 容器。
- CDP、FastAPI、PostgreSQL 和临时 VNC 端口。
- 快照输入、临时文件、日志和数据卷。

### 7.2 修改入口索引

文档必须回答“我想修改什么，应该去哪里”，至少包括：

| 目标 | 修改入口 |
| --- | --- |
| 修改固定规则中文报告 | `src/jobflow/reports/query_report.py` |
| 修改 OpenAI 总结逻辑 | `src/jobflow/ai/openai_summary.py` |
| 修改 Telegram 发送 | `src/jobflow/channels/telegram.py` |
| 修改报告接口 | `src/jobflow/api/reports.py` |
| 修改分析接口 | `src/jobflow/api/analytics.py` |
| 修改 ETL 事务流程 | `src/jobflow/workers/etl.py` |
| 修改城市、关键词或抓取范围 | 独立采集项目和 `ops/daily_update.sh` 的实际参数位置 |
| 修改每日运行时间 | `jobflow-daily-update.timer` |
| 修改数据表和 View | `migrations/*.sql` |
| 修改 Docker 服务 | `compose.yaml` 和 `Dockerfile` |

### 7.3 每个对象的记录格式

每个项目、文件、服务或容器都记录：

1. 真实路径或名称。
2. 小白化作用说明。
3. 上游和下游关系。
4. 正常状态和验收命令。
5. 修改后需要执行的重建、重启或 `daemon-reload`。
6. 常见错误和安全边界。

## 8. 公开 README 参考原则

本次参考 FastAPI、Airbyte 和 Prefect 等开源项目的 README 信息层级，只借鉴以下结构原则：

- 开头立即说明产品价值和使用对象。
- 在复杂设计之前给出最小可运行路径。
- 为不同用户提供清晰的使用路径，而不是把所有细节堆在一个章节中。
- 将完整部署、安全、贡献和运维内容链接到专题文档。

不复制其它项目的宣传文案、徽章、图片或许可声明。

## 9. 验收标准

### 9.1 公开安全

- 公开 README 和 `docs/` 中不出现个人服务器 IP、SSH 用户、个人绝对路径或个人中转服务商名称。
- 仓库和知识库不出现密码、Key、Token、Chat ID、Cookie、Webhook 或 VNC 密码实际值。
- 所有配置示例使用明显的占位值。

### 9.2 README 可用性

陌生用户可以在 README 中找到：

- 项目用途、功能边界和环境要求。
- 从 clone 到 API 健康的完整命令。
- 可执行的 JSON 快照规则和 ETL 命令。
- query 与 OpenAI 两种报告模式的差异。
- Telegram 的可选配置和推送方法。
- 项目目录树、环境变量表和 DIY 入口。
- 更详细的 Ubuntu、systemd、VNC 和排错文档链接。

### 9.3 知识库完整性

- 服务器维护区有可返回项目总览的导航。
- 每个 JobFlow 生态对象包含路径、作用、修改入口和验收命令。
- Markdown 代码围栏成对，Wiki Link 全部可解析。
- 不创建 Day 23。

### 9.4 Git

- `git diff --check` 通过。
- 提交前明确列出 V1.1 范围文件。
- 不包含 `.env`、真实数据、Chrome Profile、Cookie、VNC 密码或知识库私有文件。
- 只将 V1.1 代码、测试和公开文档提交、推送到 GitHub。

## 10. 已接受的风险与延后项

- 当前无法从 Windows 使用非交互 SSH 直接枚举服务器全部对象；服务器个人文档以本日已真实验收的 JobFlow 生态路径、服务和命令为依据。
- 正式每日 09:00 timer 的首次计划触发和连续多日运行仍待验收。
- 数据备份恢复、登录失效通知、持续监控、公网 HTTPS 和 V1.2 采集扩容不在本次范围内。
