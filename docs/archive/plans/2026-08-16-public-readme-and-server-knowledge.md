# JobFlow V1.1 Public README and Server Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 JobFlow V1.1 整理成陌生用户可从合规 JSON 快照启动的公开仓库，并在个人 Obsidian 知识库中建立真实服务器项目与维护地图。

**Architecture:** 采用三层文档边界：根 README 负责五分钟入门和项目导航，`docs/` 负责架构、Ubuntu 部署、systemd 和交接细节，个人知识库负责真实服务器地址、目录、服务关系和“修改什么应该改哪里”索引。公开仓库只使用占位符和中性 OpenAI 表述。

**Tech Stack:** Markdown、Mermaid、Docker Compose、Python 3.12、FastAPI、PostgreSQL、Bash、systemd、Telegram Bot、OpenAI Python SDK、Obsidian Wiki Link、Git/GitHub

## Global Constraints

- 默认公开入口是用户自己获得的合规 JSON 快照；BOSS Chrome/CDP 采集只是高级可选部署。
- 公开 README 和 `docs/` 不得出现个人服务器 IP、SSH 用户、个人绝对路径或个人中转服务商名称。
- 公开文档使用“OpenAI 模型”或“OpenAI 兼容接口”，不绑定具体服务商。
- `mode=query` 不调用 AI；`mode=ai` 才调用 OpenAI 模型。
- 不记录密码、API Key、Bot Token、Chat ID、Cookie、Webhook、VNC 密码或 `.env` 实际值。
- 不实施 V1.2 的抓取范围扩展，不创建 Day 23。
- 知识库保留已有 YAML、Wiki Link 和小白教程风格。
- 只向 GitHub 提交并推送 V1.1 范围；个人知识库不进入 JobFlow Git 提交。

---

## File Structure

### Repository files

- Modify: `.env.example` — 安全占位配置和 DIY 说明。
- Modify: `README.md` — 公开仓库首页、五分钟入门、架构、目录和 DIY 索引。
- Modify: `ops/daily_update.sh` — 移除个人绝对路径，从脚本位置推导 JobFlow 目录，使用可覆盖的采集器路径。
- Modify: `tests/ops/test_daily_update_script.py` — 增加公开路径和可移植性契约测试。
- Modify: `docs/README.md` — 文档阅读路径和公开/个人边界。
- Modify: `docs/reference/architecture.md` — 当前 V1.1 架构、两种报告模式和真实验收边界。
- Modify: `docs/guides/ubuntu-deployment.md` — 将个人地址和路径替换为占位符，保留通用部署与维护流程。
- Modify: `docs/project-handoff.md` — 记录 V1.1 最终交接和 V1.2 停点，不包含个人服务器信息。

### Personal knowledge-base files

- Create: `<PRIVATE_JOBFLOW_KB_ROOT>\服务器维护\JobFlow 服务器总览.md`
- Create: `<PRIVATE_JOBFLOW_KB_ROOT>\服务器维护\JobFlow 服务器项目与文件地图.md`
- Create: `<PRIVATE_JOBFLOW_KB_ROOT>\服务器维护\JobFlow 服务、容器与端口地图.md`
- Create: `<PRIVATE_JOBFLOW_KB_ROOT>\服务器维护\JobFlow 修改入口与维护手册.md`
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\JobFlow 项目总览.md`
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\每日记录\<DAY_22_NOTE>.md`
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\知识卡片\JobFlow V1.1 Ubuntu 每日自动更新小白指南.md`
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\知识卡片\JobFlow 软件与组件总览.md`

---

### Task 1: Make the V1.1 automation script portable

**Files:**
- Modify: `ops/daily_update.sh:14-17`
- Modify: `tests/ops/test_daily_update_script.py`

**Interfaces:**
- Consumes: 从 Git 检出的 JobFlow 根目录和可选 `JOBFLOW_SCRAPER_DIR` 环境变量。
- Produces: 不包含个人用户名的 `JOBFLOW_DIR`、`SCRAPER_DIR`、`PYTHON` 和 `INBOX_DIR`。

- [ ] **Step 1: Add a failing portability contract test**

```python
def test_daily_update_script_has_no_personal_absolute_paths():
    text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert 'JOBFLOW_DIR="/home/' not in text
    assert 'JOBFLOW_SCRAPER_DIR' in text
    assert 'BASH_SOURCE[0]' in text
```

- [ ] **Step 2: Run the focused test and verify that it fails**

Run:

```powershell
<JOBFLOW_PYTHON> -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: the new test fails because the script still hard-codes a personal home-directory path.

- [ ] **Step 3: Replace personal paths with repository-derived paths**

Replace lines 14-17 with:

```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
JOBFLOW_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SCRAPER_DIR="${JOBFLOW_SCRAPER_DIR:-$(dirname "$JOBFLOW_DIR")/boss-zhipin-scraper}"
PYTHON="${SCRAPER_DIR}/.venv/bin/python"
INBOX_DIR="${JOBFLOW_DIR}/data/raw/inbox"
```

- [ ] **Step 4: Run the focused contract tests**

Run:

```powershell
<JOBFLOW_PYTHON> -m pytest tests/ops/test_daily_update_script.py -q
<JOBFLOW_RUFF> check tests/ops/test_daily_update_script.py
```

Expected: all daily-script tests pass and Ruff reports no errors.

---

### Task 2: Make `.env.example` safe for first-time users

**Files:**
- Modify: `.env.example`
- Verify: `compose.yaml`
- Verify: `src/jobflow/db/connection.py`
- Verify: `src/jobflow/api/reports.py`
- Verify: `src/jobflow/ai/openai_summary.py`
- Verify: `src/jobflow/channels/telegram.py`

**Interfaces:**
- Consumes: environment names already read by Compose, psycopg, OpenAI SDK, FastAPI and Telegram channel.
- Produces: a copyable `.env.example` whose required values are obvious and whose optional proxy/AI/Telegram values do not impersonate real credentials.

- [ ] **Step 1: Group the template into required and optional settings**

Use these headings and keep the existing variable names unchanged:

```dotenv
# 1. PostgreSQL（必填）
# 2. FastAPI（可调整）
# 3. Python 依赖下载（可调整）
# 4. 网络代理（可选，无代理时留空）
# 5. OpenAI 模型（可选，只有 mode=ai 需要）
# 6. Telegram（可选，推送报告时需要）
# 7. 报告接口保护（使用报告接口时必填）
```

- [ ] **Step 2: Ensure optional network and external-service values are empty or obvious placeholders**

Rules:

```text
JOBFLOW_HTTP_PROXY=
JOBFLOW_HTTPS_PROXY=
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Keep `REPORT_TRIGGER_TOKEN=replace_with_a_long_random_token` and explain that the user must replace it before exposing the report endpoint.

- [ ] **Step 3: Render the resolved Compose configuration without displaying `.env` values**

Run:

```powershell
docker compose --profile tools config --services
```

Expected:

```text
postgres
etl
migrate
api
```

---

### Task 3: Rewrite the public README around a runnable first path

**Files:**
- Rewrite: `README.md`

**Interfaces:**
- Consumes: `compose.yaml`, `.env.example`, `pyproject.toml`, current API routes, `ops/daily_update.sh` and repository directory structure.
- Produces: a provider-neutral public landing page with a complete JSON-to-API path and optional OpenAI/Telegram path.

- [ ] **Step 1: Replace the top-level information architecture**

Use this exact section order:

```markdown
# JobFlow
## JobFlow 能做什么
## 当前状态
## 架构
## 五分钟快速开始
## 准备 JSON 快照
## 启动与导入数据
## 调用 API
## 报告与 Telegram（可选）
## 环境变量
## 项目结构
## DIY 修改入口
## Ubuntu 每日自动更新（高级）
## 测试
## 安全与数据边界
## 详细文档
```

- [ ] **Step 2: Add a provider-neutral architecture diagram**

Use Mermaid nodes for:

```text
合规 JSON 快照 -> Adapter -> ETL Worker -> PostgreSQL ops/raw/core/mart
PostgreSQL -> FastAPI -> query 固定规则报告 -> Telegram
PostgreSQL -> FastAPI -> OpenAI 模型可选总结 -> Telegram
```

- [ ] **Step 3: Add the zero-to-running command sequence**

The sequence must include:

```bash
git clone <YOUR_REPOSITORY_URL>
cd JobFlow
cp .env.example .env
mkdir -p data/raw/inbox
docker compose up -d postgres
docker compose run --rm migrate
docker compose run --rm etl /data/raw/inbox/jobs.json
docker compose up -d api
docker compose ps
curl --fail http://<API_HOST>:<API_PORT>/health
curl --fail http://<API_HOST>:<API_PORT>/ready
```

Each command block must be followed by its purpose, expected result and acceptance criterion. Explain that `<...>` is a placeholder and must be replaced without angle brackets.

- [ ] **Step 4: Document the minimum JSON envelope**

Use synthetic values only and show the required outer shape:

```json
{
  "jobs": [
    {
      "job_id": "example-001",
      "title": "数据开发工程师",
      "boss_name": "示例公司",
      "location": "示例城市·示例区域",
      "job_link": "https://example.com/jobs/example-001",
      "salary": "15-25K",
      "skills": "Python | SQL"
    }
  ]
}
```

This example matches the seven required string fields enforced by `src/jobflow/adapters/boss.py`: `job_id`, `title`, `boss_name`, `location`, `job_link`, `salary` and `skills`.

- [ ] **Step 5: Document query and OpenAI modes accurately**

Required wording:

```text
mode=query 使用固定规则生成中文简报，不调用 AI。
mode=ai 使用用户配置的 OpenAI 模型生成自然语言总结。
```

Do not mention any personal gateway. Do not claim that the V1.1 five-minute automatic acceptance used AI; it used `mode=query`.

- [ ] **Step 6: Add the project tree and DIY table**

The tree must cover `src/jobflow/adapters`, `workers`, `db`, `api`, `reports`, `ai`, `channels`, `migrations`, `ops`, `tests`, `docs`, `compose.yaml`, `Dockerfile` and `.env.example`.

The DIY table must map at least:

```text
规则报告 -> src/jobflow/reports/query_report.py
OpenAI 提示与总结 -> src/jobflow/ai/openai_summary.py
Telegram -> src/jobflow/channels/telegram.py
报告 API -> src/jobflow/api/reports.py
分析 API -> src/jobflow/api/analytics.py
ETL -> src/jobflow/workers/etl.py
数据库结构 -> migrations/*.sql
Docker -> compose.yaml / Dockerfile
自动更新 -> ops/daily_update.sh
```

- [ ] **Step 7: Check README navigation and public wording**

Run:

```powershell
Select-String -LiteralPath README.md -Pattern '^#{1,3} '
Select-String -LiteralPath README.md -Pattern '192\.168\.|/home/[^/<]+/services|\b[a-z][a-z0-9_-]*@192\.168\.'
```

Expected: headings appear in the approved order and the restricted-information search returns no matches.

---

### Task 4: Align detailed repository documentation

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/reference/architecture.md`
- Modify: `docs/guides/ubuntu-deployment.md`
- Modify: `docs/project-handoff.md`

**Interfaces:**
- Consumes: the public README terminology and the verified V1.1 status.
- Produces: provider-neutral public documentation with generic placeholders and one consistent completion boundary.

- [ ] **Step 1: Normalize public placeholders**

Replace personal values with:

```text
<SERVER_IP>
<SSH_USER>
<JOBFLOW_DIR>
<SCRAPER_DIR>
<API_HOST>
<API_PORT>
```

Every document must explain the placeholder before its first command block.

- [ ] **Step 2: Normalize OpenAI wording**

Replace personal gateway names with `OpenAI 模型` or `OpenAI 兼容接口`. Keep historical code and test facts, but do not disclose a personal provider.

- [ ] **Step 3: Synchronize the V1.1 status statement**

Use this boundary in all current-status sections:

```text
已完成五分钟完整自动链路单次真实验收；
正式 09:00 首次触发和连续多日运行仍待验收。
```

- [ ] **Step 4: Keep the handoff restartable**

`docs/project-handoff.md` must contain the V1.1 Git scope, actual test evidence, deployed component names, V1.2 deferred questions and a new-chat prompt. The public version uses placeholders; the private server map holds the actual values.

- [ ] **Step 5: Check all current public documents for restricted values**

Run:

```powershell
$files = @(
  'README.md',
  'docs/README.md',
  'docs/reference/architecture.md',
  'docs/guides/ubuntu-deployment.md',
  'docs/project-handoff.md'
)
Select-String -LiteralPath $files -Pattern '192\.168\.|/home/[^/<]+/services|\b[a-z][a-z0-9_-]*@192\.168\.'
```

Expected: no matches.

---

### Task 5: Create the private server-maintenance knowledge area

**Files:**
- Create and modify the knowledge-base files listed in **File Structure**.

**Interfaces:**
- Consumes: verified V1.1 server paths, systemd unit names, Compose services, ports and maintenance commands.
- Produces: four linked beginner-oriented notes and updated overview navigation.

- [ ] **Step 1: Create the `服务器维护` directory and four notes with existing YAML style**

Each note starts with:

```yaml
---
project: JobFlow
type: knowledge
tags:
  - project/jobflow
  - beginner
  - ubuntu
  - maintenance
---
```

- [ ] **Step 2: Write the real server overview**

Include the verified personal SSH endpoint, JobFlow root, scraper root and the V1.1 state. Credentials are described only by storage location, never by value.

- [ ] **Step 3: Write the project and file map**

Document at minimum:

```text
<PRIVATE_JOBFLOW_DIR>
<PRIVATE_SCRAPER_DIR>
<PRIVATE_CHROME_PROFILE_DIR>
/etc/systemd/system/jobflow-xvfb.service
/etc/systemd/system/jobflow-boss-chrome.service
/etc/systemd/system/jobflow-daily-update.service
/etc/systemd/system/jobflow-daily-update.timer
```

For each object, explain content, owner, upstream/downstream relationship, safe edit location and what command is required after modification.

- [ ] **Step 4: Write the service, container and port map**

Cover:

```text
Xvfb DISPLAY=:99
Chrome CDP 127.0.0.1:9222
x11vnc 127.0.0.1:5900（临时）
SSH tunnel local 127.0.0.1:15900
FastAPI host port 8000
PostgreSQL container port 5432
postgres / migrate / etl / api Compose services
```

Clearly distinguish a Linux process, a systemd unit, a Docker container, a Compose service and a network port.

- [ ] **Step 5: Write the change-entry and maintenance manual**

For every change target, include:

```text
目标 -> 本机源文件 -> 服务器文件 -> 是否 build -> 是否 restart -> 验收命令 -> 回滚思路
```

Include Docker, migration, API, query report, OpenAI, Telegram, daily script, scraper range, timer schedule, Chrome login and VNC recovery.

- [ ] **Step 6: Update knowledge-base navigation and V1.1 summary**

Add links from `JobFlow 项目总览.md`, Day 22, the V1.1 guide and the component overview. Preserve the historical provider name only inside the private historical note; current architecture wording uses OpenAI-compatible service.

---

### Task 6: Validate repository and knowledge base

**Files:**
- Verify: all changed repository and knowledge-base Markdown files.

**Interfaces:**
- Consumes: Tasks 1-5 outputs.
- Produces: evidence that documentation is structurally valid, secrets are absent, tests pass and no Day 23 was created.

- [ ] **Step 1: Run focused and regression tests sequentially**

Run:

```powershell
<JOBFLOW_PYTHON> -m pytest tests/ops/test_daily_update_script.py -q
<JOBFLOW_PYTHON> -m pytest -q
<JOBFLOW_RUFF> check .
<JOBFLOW_RUFF> format --check .
```

Expected: focused tests, full tests, Ruff check and Ruff format all pass. Run sequentially to avoid Windows temporary-file contention.

- [ ] **Step 2: Validate Markdown fences and knowledge-base links**

Use PowerShell to count lines beginning with triple backticks or tildes in every repository/knowledge-base Markdown file; every count must be even. Resolve every JobFlow `[[Wiki Link]]` against the whole Obsidian vault, not only the JobFlow subdirectory.

Expected:

```text
UnclosedFenceFiles=0
MissingJobFlowWikiLinksAgainstWholeVault=0
```

- [ ] **Step 3: Run a sensitive-information scan without printing values**

Scan repository text and JobFlow knowledge-base Markdown for OpenAI-like keys, Telegram token shapes, webhook URLs and literal assignments to password/token variables. Print only match counts and file/line locations, never matching contents.

Expected:

```text
SuspiciousSecretLocations=0
```

- [ ] **Step 4: Confirm no future daily note exists**

Run:

```powershell
Get-ChildItem -LiteralPath '<PRIVATE_JOBFLOW_KB_ROOT>\每日记录' -File |
  Where-Object { $_.Name -match 'Day 23' }
```

Expected: no output.

- [ ] **Step 5: Validate Git whitespace and inventory**

Run:

```powershell
git diff --check
git status --short --branch
git log -5 --oneline
git diff origin/main --name-status
```

Expected: no whitespace errors; all outgoing files belong to V1.1 documentation, automation, tests or design history.

---

### Task 7: Commit and push only V1.1

**Files:**
- Stage: `.env.example`, `README.md`, `docs/`, `ops/daily_update.sh`, `tests/ops/test_daily_update_script.py`
- Exclude: `.env`, runtime data, logs, caches, Chrome Profile, Cookie, VNC credentials and the personal Obsidian vault.

**Interfaces:**
- Consumes: validated V1.1 repository changes.
- Produces: a GitHub `main` branch containing the V1.1 code, tests and public documentation only.

- [ ] **Step 1: Stage only the explicit V1.1 paths**

Run:

```powershell
git add -- .env.example README.md docs ops/daily_update.sh tests/ops/test_daily_update_script.py
git diff --cached --name-status
git diff --cached --check
```

Expected: the staged inventory contains only V1.1 files and no private knowledge-base path or local `.env`.

- [ ] **Step 2: Re-run the sensitive-information count on staged content**

Inspect `git diff --cached` through a scanner that reports only file/line locations. If any match appears, unstage the affected file, remove the value and repeat validation.

- [ ] **Step 3: Create the final V1.1 commit**

Run:

```powershell
git commit -m "feat: 完成 V1.1 每日更新与公开文档"
```

Expected: the commit succeeds and includes only the reviewed staged inventory.

- [ ] **Step 4: Push the verified V1.1 branch to GitHub**

Run:

```powershell
git push origin main
git status --short --branch
git log -5 --oneline
```

Expected: push succeeds; `main...origin/main` has no ahead/behind count. Any intentionally excluded local changes are reported separately.
