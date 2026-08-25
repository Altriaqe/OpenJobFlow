# JobFlow 公开仓库 README 与可复现体验设计

日期：2026-08-25
状态：已批准，待实施计划
范围：公开 README、许可证、虚构示例数据和 README 演示素材

## 1. 背景与目标

JobFlow 当前已经实现招聘 JSON 快照校验、PostgreSQL 分层 ETL、FastAPI 只读分析、可选 OpenAI-compatible 总结、Telegram 图文推送和 Ubuntu 定时运行。现有 README 包含大量真实演进历史和高级运维信息，但缺少面向陌生开发者的清晰产品定位、完整双语入口和仓库内可直接使用的虚构样本。

本轮目标是把仓库首页调整为适合公开开源的入口，使第一次访问的开发者能够：

1. 快速理解 JobFlow 是“开源招聘数据智能流水线 / 轻量级 AI 数据平台”；
2. 在不安装本机 Python、不配置 AI、不配置 Telegram 的情况下，通过 Docker 和虚构 JSON 样本复现基础链路；
3. 理解数据层、模块、技术栈和可选高级能力；
4. 明确数据授权、安全和非生产级边界；
5. 根据文档继续配置 AI、Telegram 或 Ubuntu 服务器。

## 2. 参考项目与采用原则

信息结构参考以下公开项目：

- [DataHub](https://github.com/datahub-project/datahub)：价值定位、架构说明、Quick Start 和源码开发路径分层；
- [OpenMetadata](https://github.com/open-metadata/OpenMetadata)：先解释平台价值和数据/AI 上下文，再展开架构与使用方式；
- [Dify](https://github.com/langgenius/dify)：Quick Start、Key Features、Advanced Setup、Contributing、Security 和 License 的首页顺序；
- [Airbyte](https://github.com/airbytehq/airbyte)：为不同用户区分入门路径和高级部署路径；
- [MindsDB](https://github.com/mindsdb/mindsdb)：Get Started、能力、内部组件、部署和社区入口分层。

只借鉴信息架构和阅读顺序，不复制这些项目的宣传文案、图片、徽标或代码。JobFlow 的能力描述必须由当前代码、测试和真实验收支持。

## 3. 目标读者与定位

### 3.1 主要读者

- 希望通过 Docker 运行招聘数据 ETL 和分析 API 的普通开发者；
- 学习 Python、PostgreSQL、FastAPI 和数据分层的开发者；
- 希望把结构化指标接入 OpenAI-compatible 模型或 Telegram 的自部署用户。

### 3.2 一句话定位

中文：

> JobFlow 是一个开源招聘数据智能流水线和轻量级 AI 数据平台，将合规 JSON 快照转换为 PostgreSQL 分层数据、只读分析 API、趋势简报和可选消息推送。

英文：

> JobFlow is an open-source recruitment intelligence pipeline and lightweight AI data platform that turns compliant JSON snapshots into layered PostgreSQL data, read-only analytics APIs, trend briefs, and optional message delivery.

不使用“企业级 AI 数据中台”作为主定位，因为当前没有多租户、权限中心、数据目录、编排 UI、监控和高可用能力。

## 4. 文件范围

实施阶段只修改或新增：

```text
README.md                     英文完整主入口
README.zh-CN.md               中文完整镜像
LICENSE                       标准 MIT 许可证
examples/jobs.sample.json     完全虚构、可直接导入的岗位样本
docs/assets/jobflow-demo.png  使用虚构数据生成的日报演示图
docs/README.md                必要的双语 README 或演示记录入口
```

不修改 ETL、API、数据库 Schema、Migration、服务器配置或生产 timer。现有 `README.md` 中仍然正确的技术说明可以迁移到双语结构中；真实运维历史继续由 `docs/` 保存，不全部堆叠在公开首页。

## 5. README 信息架构

`README.md` 和 `README.zh-CN.md` 使用相同的章节顺序、命令、链接和能力边界。

### 5.1 首页首屏

1. 项目名称；
2. 英文/中文语言切换；
3. 一句话定位；
4. Python 3.12、FastAPI、PostgreSQL、Docker Compose 和 MIT 静态徽章；
5. 基于虚构数据的演示图；
6. 数据为虚构演示数据的醒目标注。

不添加尚不存在的 CI、覆盖率、版本发布或生产可用徽章。

### 5.2 正文章节

```text
Why JobFlow / 为什么使用 JobFlow
Key Features / 核心能力
Architecture / 架构与数据流
Quick Start / 10 分钟 Docker 复现
API and Demo Output / API 与演示效果
Technology Stack / 技术栈
Project Structure / 项目结构
Optional AI Summary / 可选 AI 总结
Optional Telegram Delivery / 可选 Telegram 推送
Ubuntu Deployment / Ubuntu 简明部署
Configuration and DIY / 配置与 DIY 入口
Development and Testing / 本地开发与测试
Data, Security and Compliance / 数据、安全与合规
Roadmap / 路线图
Contributing / 参与贡献
License / 许可证
Documentation / 详细文档
```

服务器 systemd、VNC、Mihomo 和恢复操作只在 README 中提供概览，并链接 `docs/ubuntu-deployment.md`。完整命令不重复复制到首页。

## 6. 默认复现路径

### 6.1 基础要求

- Git；
- Docker Engine 或 Docker Desktop；
- Docker Compose v2，命令为 `docker compose`；
- 本机端口 `8000` 和 `5432` 可用，或在 `.env` 中修改；
- 仅使用 Docker 时，宿主机不要求安装 Python。

### 6.2 Linux/macOS 路径

```bash
git clone https://github.com/Altriaqe/JobFlow.git
cd JobFlow
cp .env.example .env
mkdir -p data/raw/inbox
cp examples/jobs.sample.json data/raw/inbox/jobs.json
```

### 6.3 Windows PowerShell 路径

```powershell
git clone https://github.com/Altriaqe/JobFlow.git
Set-Location JobFlow
Copy-Item .env.example .env
New-Item -ItemType Directory -Force data/raw/inbox | Out-Null
Copy-Item examples/jobs.sample.json data/raw/inbox/jobs.json
```

用户必须把 `.env` 中的示例数据库密码替换为自己的本地密码。README 只展示变量名和占位符，不展示维护者的实际值。

### 6.4 启动顺序

```bash
docker compose up -d postgres
docker compose run --rm migrate
docker compose run --rm etl /data/raw/inbox/jobs.json
docker compose up -d api
docker compose ps
```

README 对每个命令说明目标、作用、预期结果和验收标准。默认路径不要求 OpenAI、Telegram、Mihomo、systemd 或外部采集器。

### 6.5 验收

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail 'http://127.0.0.1:8000/analytics/cities?limit=20'
```

Windows README 同时给出 PowerShell 可执行的 `Invoke-RestMethod` 示例。

成功标准：

- ETL 输出完成状态；
- PostgreSQL 和 API 正常运行；
- `/health` 返回进程健康；
- `/ready` 确认 PostgreSQL 可连接；
- 城市分析接口返回虚构样本聚合；
- `http://127.0.0.1:8000/docs` 可打开 Swagger UI。

## 7. 虚构示例数据

`examples/jobs.sample.json` 必须符合当前 Adapter 的真实七字段契约：

```text
job_id
title
boss_name
location
job_link
salary
skills
```

所有公司、岗位链接和业务内容均为虚构。样本覆盖：

- 多个城市；
- 多个岗位方向；
- 普通 K 薪资、人民币月薪和“面议”等当前已支持格式；
- 多个技能组合；
- 足以让城市、薪资和技能 API 返回非空结果。

示例链接使用 `example.com`，不得使用真实招聘网站 URL。文件中增加可识别的示例 ID，不包含从真实快照脱敏而来的记录。

## 8. 演示图片

`docs/assets/jobflow-demo.png` 使用虚构样本或与虚构样本一致的聚合数据，通过 JobFlow 当前 `reports/charts.py` 图表能力生成。

要求：

- 图片内容与当前代码能力一致；
- 不手工制作不存在的 UI；
- 不使用私人 Telegram、服务器或浏览器截图；
- 图注明确说明 synthetic demo data / 虚构演示数据；
- 中英文 README 共用同一张无个人信息的图片；
- 图片在 GitHub 浅色和深色页面中均可辨认。

## 9. 技术栈与模块边界

README 按当前实现说明：

| 层级 | 技术 | 职责 |
| --- | --- | --- |
| 语言与运行时 | Python 3.12 | Adapter、ETL、API、报告与渠道逻辑 |
| 数据库 | PostgreSQL 18 | `ops/raw/core/mart`、事务、View 与快照 |
| API | FastAPI + Uvicorn | 健康、聚合查询和报告接口 |
| 数据访问 | Psycopg 3 | 参数化 SQL、事务与批量写入 |
| AI | OpenAI-compatible API | 可选总结固定结构化指标 |
| 图表 | Matplotlib | 关键词和城市趋势图 |
| 渠道 | Telegram Bot API | 可选图文推送 |
| 部署 | Docker + Docker Compose | PostgreSQL、Migration、ETL 与 API |
| 自动化 | Bash + systemd | Ubuntu 每日任务和失败保护 |
| 网络 | Mihomo 覆盖配置 | 网络受限部署的可选应用代理 |
| 质量 | Pytest + Ruff | 单元、契约、集成测试和静态检查 |

源码模块与职责：

```text
adapters     来源格式隔离、字段校验、薪资与技能标准化
workers      ETL 批次、事务提交和失败回滚
db           PostgreSQL 连接、写入与固定分析 SQL
reports      查询简报、日/周比较和图表
ai           OpenAI-compatible 总结适配
channels     Telegram 等消息输出
api          健康、分析和报告接口
migrations   ops/raw/core/mart 结构演进
ops          Ubuntu 每日任务编排
```

## 10. 可选高级能力

### 10.1 AI 总结

- `mode=query` 不需要 AI Key；
- `mode=ai` 才读取 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 和 `OPENAI_MODEL`；
- AI 只处理固定查询返回的结构化统计；
- AI 不获得数据库凭据，也不直接执行 SQL。

### 10.2 Telegram

- 使用部署者自己的 Bot Token 和 Chat ID；
- 报告触发接口使用独立 Bearer Token；
- 不确定发送结果不会由普通接口自动重试；
- 只补图恢复流程链接详细运行手册，不在 Quick Start 中展开。

### 10.3 Ubuntu 与自动采集

- 自动采集器是独立项目，不随 JobFlow 发布；
- 使用者必须自行提供合法授权的采集器并人工处理登录与平台安全验证；
- JobFlow 不提供绕过验证码、风控、登录限制或访问控制的能力；
- README 只展示 Ubuntu 部署概览，详细操作链接 `docs/ubuntu-deployment.md`。

### 10.4 网络代理

- 默认部署保持直连；
- `compose.proxy.yaml` 是网络受限环境的可选覆盖；
- 代理订阅、节点和凭据由部署者私下维护；
- 公开文档只展示占位符和接口，不展示维护者配置。

## 11. MIT 许可证与数据边界

仓库根目录增加标准 MIT License：

```text
Copyright (c) 2026 Altriaqe
```

不自行修改 MIT 正文。README 额外明确：

- MIT 只授权 JobFlow 自有代码和文档；
- 不授权第三方网站内容、招聘数据、商标或用户凭据；
- 示例数据完全虚构；
- 项目用于学习、研究和合法技术实践；
- 使用者必须自行取得数据权限并遵守平台条款、隐私要求和当地法律；
- 维护者不对使用者的数据来源、部署方式或第三方服务行为背书。

## 12. 个人配置与秘密保护

公开仓库不得出现：

- `.env` 实值；
- 服务器 IP、用户名、个人目录和 Tailscale 地址；
- API Key、Telegram Token、触发 Token 和 Chat ID；
- Cookie、Chrome Profile、VNC 密码或私钥；
- Mihomo 订阅链接、节点和代理凭据；
- 真实招聘快照、个人 Telegram 截图和包含个人运行环境的终端截图。

文档使用 `<YOUR_...>`、`<SERVER_IP>`、`<JOBFLOW_DIR>` 等占位符。公开 README 不引用私有 Obsidian 路径。

## 13. 实施验收

### 13.1 内容一致性

- 中英文 README 章节、命令、变量和链接一致；
- 英文 `README.md` 与中文 `README.zh-CN.md` 顶部互相跳转；
- 不把设计、计划或单次测试写成生产级承诺；
- 不硬编码容易过时的测试数量。

### 13.2 干净环境复现

在干净目录中按 README 执行：

```text
复制 .env
复制虚构样本
启动 PostgreSQL
执行 Migration
执行 ETL
启动 API
验证 /health、/ready、分析接口和 /docs
```

### 13.3 工程检查

- `docker compose config --quiet`；
- Pytest；
- Ruff check 与 format check；
- Markdown 相对链接和图片路径检查；
- JSON 语法及 Adapter 契约验证；
- 公开文件敏感信息扫描；
- Git 暂存范围检查。

### 13.4 提交边界

README 实现提交只包含第 4 节列出的公开化文件。现有 `.superpowers/` 临时目录、历史未提交文档和私人配置不得混入。完成实现与验收后，先向用户展示差异和验证结果；未经用户再次授权，不提交或推送 README 实现。

## 14. 非目标

本轮不实现：

- 一键安装脚本、Makefile 或新的 CLI；
- GitHub Actions、覆盖率服务或发布自动化；
- Web 分析界面；
- 新的数据采集器；
- 多租户、权限中心、数据目录、监控、高可用或公网 HTTPS；
- 图表系统重构；
- 生产服务器配置变更。

## 15. 完成定义

同时满足以下条件才算完成：

1. 英文和中文 README 均可独立指导陌生用户完成 Docker 基础复现；
2. 仓库包含标准 MIT License 和完全虚构的示例数据；
3. 演示图由当前 JobFlow 图表能力使用虚构数据生成；
4. 基础复现不依赖 AI、Telegram、代理、外部采集器或维护者个人环境；
5. 技术栈、模块、能力与未完成边界和当前代码一致；
6. 敏感信息、真实数据和个人配置扫描无命中；
7. README 实现的提交范围与验收结果经用户确认。
