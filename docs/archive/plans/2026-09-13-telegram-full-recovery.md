# Telegram 全量恢复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为文字和图片均未收到、但文字投递结果为 `text_uncertain` 的日报增加一次性、显式确认的 Telegram 全量恢复入口。

**Architecture:** 复用现有多关键词日报构建和发送函数，仅新增恢复编排函数与受保护 API 路由。恢复只接受统一的 `confirm_not_received=true`，先锁定并验证整组快照处于 `text_uncertain`、无消息 ID，再重新发送文字；文字明确成功后才发送图片，任一步结果不确定立即停止。

**Tech Stack:** Python 3.12, FastAPI, PostgreSQL 状态表, pytest.

## Global Constraints

- 不修改普通 `/reports/daily/multi/send` 语义。
- 不重置数据库、不删除历史投递记录、不暴露 Token 或消息 ID。
- Telegram 文字发送结果不确定时禁止继续发送图片。
- 只允许有完整四关键词快照的指定日期执行恢复。

---

### Task 1: 添加恢复服务的失败测试

**Files:**
- Modify: `tests/reports/test_multi_keyword_service.py`
- Modify: `src/jobflow/reports/multi_keyword_service.py`

**Interfaces:**
- Produces: `recover_multi_keyword_report(connection, snapshot_date, confirm_not_received, text_sender=None, photo_sender=None)`.

- [ ] **Step 1: 添加成功路径测试**

验证 `text_uncertain` 整组状态可重新发送文字和图片，并返回 `status=sent`。

- [ ] **Step 2: 添加保护测试**

验证未确认、非 `text_uncertain`、文字再次不确定时，恢复会停止且不发送图片。

- [ ] **Step 3: 运行定向测试确认失败**

```powershell
pytest tests/reports/test_multi_keyword_service.py -q
```

预期：新增测试在恢复函数不存在或状态校验未实现时失败。

- [ ] **Step 4: 实现最小恢复编排**

锁定四条投递记录，确认状态为 `completed_text_uncertain` 或 `text_uncertain` 对应的完整文字不确定状态；本次当前数据是 `text_uncertain`，只允许该状态。认领文字、调用文字发送器、明确成功后认领图片并调用图片发送器，沿用既有错误记录函数。

- [ ] **Step 5: 运行报告测试**

```powershell
pytest tests/reports/test_multi_keyword_service.py -q
```

预期：全部通过。

### Task 2: 添加受保护恢复 API

**Files:**
- Modify: `src/jobflow/api/reports.py`
- Modify: `tests/api/test_reports.py`

**Interfaces:**
- Consumes: `recover_multi_keyword_report` dependency provider.
- Produces: `POST /reports/daily/multi/recover?snapshot_date=YYYY-MM-DD&confirm_not_received=true`.

- [ ] **Step 1: 添加 API 鉴权、确认和转发测试**

验证无 Token 返回 `401`，无确认返回 `409`，有确认时传入连接和日期并返回安全状态。

- [ ] **Step 2: 运行 API 定向测试确认失败**

```powershell
pytest tests/api/test_reports.py -q
```

- [ ] **Step 3: 实现 provider、路由和异常映射**

将状态缺失映射为 `409`，Telegram 明确失败或不确定映射为 `502`，不返回消息 ID。

- [ ] **Step 4: 运行 API 测试**

```powershell
pytest tests/api/test_reports.py -q
```

预期：全部通过。

### Task 3: 完成回归检查和部署前复核

**Files:**
- Modify: `docs/guides/ubuntu-deployment.md`
- Modify: `docs/project-handoff.md`

- [ ] **Step 1: 增加恢复命令说明**

只记录占位符命令和“先确认手机未收到，再调用专用恢复接口”的边界，不记录任何真实凭据。

- [ ] **Step 2: 运行最小完整检查**

```powershell
pytest tests/reports/test_multi_keyword_service.py tests/api/test_reports.py -q
ruff check src tests
git diff --check
```

- [ ] **Step 3: 复核服务端部署前提**

确认本地测试通过后再提交；部署服务器前必须先确认服务器 Git 工作区、API 镜像和今天 Telegram 数据库状态，不能直接执行普通发送接口。
