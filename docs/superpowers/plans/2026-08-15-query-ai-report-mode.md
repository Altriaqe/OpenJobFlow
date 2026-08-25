# 查询与 AI 双模式报告实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为城市报告接口增加默认查询模式和可选 AI 模式，并生成专业、可核验的查询简报。

**Architecture:** API 接收 `mode` 参数并默认使用 `query`；报告服务读取同一批城市指标，根据模式选择固定规则报告生成器或现有 OpenAI 兼容服务/OpenAI 生成器，最后统一交给 Telegram 发送器。数据库、ETL、鉴权和发送渠道保持不变。

**Tech Stack:** Python 3.12、FastAPI、Pydantic/FastAPI 参数校验、pytest、现有 PostgreSQL analytics 查询、Telegram Bot API。

## Global Constraints

- `query` 是默认模式，`ai` 是可选模式。
- 查询模式不得调用 AI 或外部网络。
- AI 模式只使用输入的城市和岗位数量，不编造薪资、技能、趋势、原因或不存在的数字。
- 空数据返回 `skipped`，不调用 AI、不发送 Telegram。
- Bearer Token 鉴权失败时不得查询数据库或调用外部服务。
- 不修改 ETL、PostgreSQL 表结构、Telegram 密钥和现有 `.env` 实际值。
- 不自动 commit 或 push；每个任务完成后的提交动作必须等待用户明确授权。

---

### Task 1: 固定规则查询报告生成器

**Files:**
- Create: `src/jobflow/reports/query_report.py`
- Modify: `tests/reports/test_query_report.py`

**Interfaces:**
- Consumes: `rows: list[dict[str, object]]`，每项包含 `city` 和 `job_count`。
- Produces: `build_query_report(rows) -> str`；空列表返回空字符串或由服务层提前跳过，最终不得触发发送。

- [ ] **Step 1: 写失败测试**

测试至少覆盖：总量、城市数、第一名、前三占比、排名表、口径说明，以及空数据不生成带数字的报告。

```python
def test_build_query_report_contains_metrics_and_disclaimer():
    report = build_query_report([
        {"city": "杭州", "job_count": 96},
        {"city": "上海", "job_count": 82},
        {"city": "深圳", "job_count": 85},
    ])
    assert "职位总量：263 个" in report
    assert "最高城市岗位数：杭州，96 个" in report
    assert "口径说明" in report
    assert "不代表完整招聘市场规模" in report
```

- [ ] **Step 2: 运行测试确认失败**

运行：`conda run -n jobflow pytest -q tests/reports/test_query_report.py`

预期：FAIL，原因是 `jobflow.reports.query_report` 尚不存在。

- [ ] **Step 3: 实现最小生成器**

实现固定模板：报告标题、生成时间、数据范围、核心指标、城市排名、数据观察、业务提示和口径说明。排序按 `job_count` 降序；占比为岗位数除以总量，保留 1 位小数；没有历史快照时明确写“无法判断趋势”。观察文字只能由岗位数、排名和占比规则生成。

- [ ] **Step 4: 运行测试确认通过**

运行：`conda run -n jobflow pytest -q tests/reports/test_query_report.py`

预期：该文件全部 PASS，且报告中不出现 OpenAI、OpenAI 兼容服务 或密钥字段。

- [ ] **Step 5: 提交前暂停**

检查：`git diff -- src/jobflow/reports/query_report.py tests/reports/test_query_report.py`。是否提交由用户另行授权。

### Task 2: 报告服务增加模式选择

**Files:**
- Modify: `src/jobflow/reports/service.py`
- Modify: `tests/reports/test_service.py`

**Interfaces:**
- Consumes: `build_query_report()` 和现有 `generate_city_report()`。
- Produces: `send_city_report(connection, *, mode="query", summary_generator=..., sender=...) -> dict[str, object]`。

- [ ] **Step 1: 写失败测试**

增加以下断言：默认模式调用查询生成器且不调用 AI；`mode="ai"` 调用 AI；非法模式抛出明确的 `ValueError`；空数据两种模式都跳过。

```python
def test_default_mode_does_not_call_ai(monkeypatch):
    ai = Mock()
    query = Mock(return_value="固定查询简报")
    sender = Mock()
    monkeypatch.setattr(service, "build_query_report", query)
    result = send_city_report(connection_with_rows([("杭州", 12)]), summary_generator=ai, sender=sender)
    query.assert_called_once()
    ai.assert_not_called()
    assert result == {"status": "sent", "city_count": 1}
```

- [ ] **Step 2: 运行测试确认失败**

运行：`conda run -n jobflow pytest -q tests/reports/test_service.py`

预期：FAIL，原因是服务函数尚未接收或处理 `mode`。

- [ ] **Step 3: 实现模式分派**

在查询完成并转换为现有 rows 后：`query` 调用 `build_query_report(rows)`；`ai` 调用传入的 `summary_generator(rows)`；其他模式抛出 `ValueError("unsupported report mode")`。发送器逻辑和返回结构保持不变。

- [ ] **Step 4: 运行聚焦测试**

运行：`conda run -n jobflow pytest -q tests/reports/test_service.py tests/ai/test_openai_summary.py tests/channels/test_telegram.py`

预期：全部 PASS。

- [ ] **Step 5: 提交前暂停**

检查服务 diff 和测试结果，等待用户授权后再决定是否提交。

### Task 3: API 参数校验与回归测试

**Files:**
- Modify: `src/jobflow/api/reports.py`
- Modify: `tests/api/test_reports.py`
- Modify: `README.md`（仅在用户要求同步文档或授权后）

**Interfaces:**
- Consumes: `mode: Literal["query", "ai"] = "query"` 和报告服务的 `mode` 参数。
- Produces: `POST /reports/cities/send[?mode=query|ai]`，非法值由 FastAPI 返回 422。

- [ ] **Step 1: 写 API 失败测试**

测试默认模式、显式 `query`、显式 `ai` 都把正确模式传给依赖；非法值返回 422；无 Token 仍在服务调用前返回 401。

- [ ] **Step 2: 运行测试确认失败**

运行：`conda run -n jobflow pytest -q tests/api/test_reports.py`

预期：新增模式测试 FAIL，既有鉴权测试保持通过。

- [ ] **Step 3: 实现参数校验**

使用 FastAPI 的 `Literal["query", "ai"]` 查询参数，默认值为 `"query"`，调用 `report_sender(connection, mode=mode)`。保留现有异常到 502/503 的映射。

- [ ] **Step 4: 运行完整非集成回归**

运行：`conda run -n jobflow pytest -q -m "not integration"`，再运行 `ruff check .` 和 `ruff format --check .`。

预期：测试、Ruff 检查和格式检查全部通过。

- [ ] **Step 5: Ubuntu 验收前暂停**

先向用户报告 Windows 验收结果和待变更文件；未经明确授权不提交、不推送、不重建 Ubuntu 镜像。得到授权后，再按 `docs/ubuntu-deployment.md` 在 SSH 会话中分别验证 `mode=query` 和 `mode=ai`，且不展示任何密钥或 Token。

## 验收结果定义

- “查询模式已实现”：Windows 测试证明不调用 AI，且固定报告内容正确。
- “AI 模式已实现”：Windows Mock 测试证明分派逻辑正确。
- “AI 真实接入”：Ubuntu 通过 OpenAI 兼容服务 实际生成并成功发送 Telegram，必须单独记录外部联调证据。
- “第一版完成”：两种模式、接口鉴权、Telegram 发送、测试和文档均完成，并由用户决定是否提交 Git。
