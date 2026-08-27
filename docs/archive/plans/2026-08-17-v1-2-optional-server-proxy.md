# JobFlow V1.2 Optional Server Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 JobFlow 提供不影响默认部署的可选 Mihomo 服务器代理覆盖，并完成公开文档、真实 Ubuntu 迁移和知识库同步。

**Architecture:** 默认 `compose.yaml` 保持直连；`compose.proxy.yaml` 只在用户显式指定时加入 Mihomo，并覆盖 API 的标准代理环境变量。订阅配置由公开模板复制到 Git 忽略的 `runtime/mihomo`，代理端口只存在于 Compose 内部网络。

**Tech Stack:** Docker Compose、Mihomo v1.19.30、pytest、Markdown、Ubuntu 22.04

## Global Constraints

- 不记录或输出真实订阅、节点、Token、Cookie、密码和 `.env` 值。
- 不修改默认直连部署行为。
- Mihomo 不配置 `ports`。
- 用户亲手执行 Ubuntu 迁移命令。
- 未经明确授权不 commit 或 push。
- 只把实际验证完成的状态写入交接和知识库。

---

### Task 1: Add Failing Proxy Deployment Contract Tests

**Files:**
- Create: `tests/ops/test_proxy_deployment_files.py`
- Inspect: `compose.proxy.yaml`
- Inspect: `deploy/mihomo/config.example.yaml`
- Inspect: `.gitignore`

**Interfaces:**
- Produces: 对镜像版本、内部端口、代理地址、订阅占位符和运行目录忽略规则的静态契约。

- [ ] **Step 1: 写失败测试**

测试必须断言：

```python
assert "metacubex/mihomo:v1.19.30" in proxy_compose
assert "restart: unless-stopped" in proxy_compose
assert "http://mihomo:7890" in proxy_compose
assert "expose:" in proxy_compose
assert "ports:" not in mihomo_service_block
assert "<YOUR_PROXY_SUBSCRIPTION_URL>" in config_template
assert "runtime/" in gitignore_lines
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
& '<JOBFLOW_PYTHON>' -m pytest tests\ops\test_proxy_deployment_files.py -q
```

Expected: FAIL，因为三个部署文件尚未创建或更新。

---

### Task 2: Implement the Optional Compose Overlay

**Files:**
- Create: `compose.proxy.yaml`
- Create: `deploy/mihomo/config.example.yaml`
- Modify: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: Compose 服务名 `mihomo`、内部代理 `http://mihomo:7890`、配置目录 `${MIHOMO_CONFIG_DIR:-./runtime/mihomo}`。

- [ ] **Step 1: 新增覆盖文件**

```yaml
services:
  mihomo:
    image: metacubex/mihomo:v1.19.30
    restart: unless-stopped
    volumes:
      - "${MIHOMO_CONFIG_DIR:-./runtime/mihomo}:/root/.config/mihomo"
    command: ["-d", "/root/.config/mihomo"]
    expose:
      - "7890"

  api:
    environment:
      HTTP_PROXY: http://mihomo:7890
      HTTPS_PROXY: http://mihomo:7890
      NO_PROXY: postgres,mihomo,localhost,127.0.0.1
    depends_on:
      mihomo:
        condition: service_started
```

- [ ] **Step 2: 新增公开配置模板**

模板使用 Provider、`AUTO` url-test、内部 `mixed-port: 7890` 和唯一订阅占位符 `<YOUR_PROXY_SUBSCRIPTION_URL>`。

- [ ] **Step 3: 更新环境模板和忽略规则**

`.env.example` 增加：

```dotenv
MIHOMO_CONFIG_DIR=./runtime/mihomo
```

`.gitignore` 增加：

```gitignore
runtime/
```

- [ ] **Step 4: 跑测试和 Compose 合并检查**

```powershell
& '<JOBFLOW_PYTHON>' -m pytest tests\ops\test_proxy_deployment_files.py -q
docker compose config --quiet
docker compose -f compose.yaml -f compose.proxy.yaml config --quiet
```

Expected: tests pass；两种 Compose 模式均退出 0。

---

### Task 3: Update V1.2 Public Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/guides/ubuntu-deployment.md`
- Modify: `docs/reference/architecture.md`
- Modify: `docs/project-handoff.md`
- Modify: `docs/README.md`

**Interfaces:**
- Consumes: Task 2 的真实文件名和命令。
- Produces: 默认直连、可选代理、一键启动、配置检查、验收和回滚说明。

- [ ] **Step 1: README 写两条部署路径**

明确默认命令不变；代理部署使用：

```bash
docker compose -f compose.yaml -f compose.proxy.yaml up -d postgres api mihomo
```

- [ ] **Step 2: 部署与架构文档写安全边界**

解释 `expose` 与 `ports`、Compose DNS、私有运行目录、容器 `127.0.0.1`、Docker daemon 拉取代理不在本功能范围内。

- [ ] **Step 3: 交接标注层级**

代码实现与本机配置验证完成后写“本机已验证”；只有 Ubuntu 迁移和真实发送完成后写“服务器真实验收”。

---

### Task 4: Run Regression and Request Git Authorization

**Files:**
- All repository files from Tasks 1–3

- [ ] **Step 1: 定向与非集成回归**

```powershell
& '<JOBFLOW_PYTHON>' -m pytest tests\ops -q
& '<JOBFLOW_PYTHON>' -m pytest --ignore=tests\integration -q
& '<JOBFLOW_RUFF>' check .
& '<JOBFLOW_RUFF>' format --check .
git diff --check
```

- [ ] **Step 2: 等待明确授权**

不执行 `git add`、`git commit` 或 `git push`，直到用户授权。

---

### Task 5: Migrate the Personal Ubuntu Server

**Files:**
- Private: `/etc/jobflow-mihomo/config.yaml`
- Repository runtime target via `.env`: `MIHOMO_CONFIG_DIR=/etc/jobflow-mihomo`

**Interfaces:**
- Consumes: 已推送的 V1.2 文件与现有私有配置。
- Produces: Compose 管理的 `mihomo` 服务。

- [ ] **Step 1: 备份并处理服务器 Git 未跟踪 `ops/`**

先比较、项目外备份并保留现有可执行脚本；只允许 `git pull --ff-only`。

- [ ] **Step 2: 停止旧独立容器并启动覆盖栈**

```bash
docker stop jobflow-mihomo
docker rm jobflow-mihomo
docker compose -f compose.yaml -f compose.proxy.yaml up -d postgres api mihomo
```

`.env` 中设置 `MIHOMO_CONFIG_DIR=/etc/jobflow-mihomo`，但不显示整个文件。

- [ ] **Step 3: 真实验收**

检查 Compose 服务、`port_bindings={}`、API `HTTPS_PROXY`、Docker DNS、Telegram `getMe`、`mode=query` 和手机实收。

---

### Task 6: Synchronize the Private Knowledge Base

**Files:**
- Modify: `JobFlow Day 23 - Ubuntu Mihomo 长期代理.md`
- Modify: `Mihomo 与 Docker 内部代理小白指南.md`
- Modify: server maps, Docker commands, project overview, V1.1 guide and glossary

- [ ] **Step 1: 把独立 `docker run` 更新为 V1.2 Compose 管理方式**

保留迁移历史，但把日常维护命令切换为带两个 `-f` 的 Compose 命令。

- [ ] **Step 2: 运行围栏、Wiki Link 和敏感信息检查**

Expected: 围栏成对、链接可解析、无真实订阅和 Token。

- [ ] **Step 3: 最终 Git 状态与完成边界**

说明公开仓库提交状态、Ubuntu 实际提交、即时真实验收、下一次正式 timer 和连续多日边界。
