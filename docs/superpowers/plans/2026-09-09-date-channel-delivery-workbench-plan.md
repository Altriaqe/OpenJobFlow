# 按日期按渠道投放工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 JobFlow Operations 中台上实现一个按日期、按渠道、带状态保护的日常投放工作台。

**Architecture:** 新增一个小型 operations 服务层，统一计算日期资格和 Telegram/微信渠道状态；FastAPI 返回指定日期的工作台快照，现有投放路由在调用外部渠道前复用同一套规则。Streamlit 只展示状态、发起管理员操作并在操作后刷新，不直接执行 SQL 或自行判断幂等。

**Tech Stack:** Python 3.12、FastAPI、Streamlit、PostgreSQL、pytest，以及现有投放状态表。

## Global Constraints

- 历史日期复用已有快照，不重新抓取；当天无快照时显示未准备，不隐式启动完整链路。
- 未来日期由前后端共同禁止抓取和投放。
- Telegram 与微信状态和动作独立；一个渠道失败不影响另一个。
- 成功状态禁止重复投放；明确失败允许重试；不确定状态须显式确认外部未收到。
- 微信只创建草稿，不调用发布接口。
- 不返回 Token、AppSecret、Webhook、Cookie、Chat ID、完整素材 ID 或完整请求 URL。
- 不引入新依赖、状态表、多租户或实时推送。
- 保留工作区已有用户改动，不在任务提交中混入无关文件。

---

## File Map

- Create: `src/jobflow/operations/delivery_workbench.py` — 日期资格、统一渠道状态和动作策略。
- Create: `tests/operations/test_delivery_workbench.py` — 日期和渠道状态纯逻辑测试。
- Modify: `src/jobflow/api/dashboard.py` — 指定日期工作台只读接口。
- Modify: `src/jobflow/api/reports.py` — 投放前日期/状态校验和不确定结果确认。
- Modify: `tests/api/test_dashboard_deliveries.py`、`tests/api/test_reports.py`、`tests/api/test_wechat_reports.py` — API 合同测试。
- Modify: `src/jobflow/dashboard/app.py`、`src/jobflow/dashboard/components.py` — 工作台交互和展示。
- Modify: `tests/dashboard/test_dashboard_contract.py` — 页面合同测试。
- Modify: `docs/guides/ubuntu-deployment.md` — 部署和人工验收步骤。

## Stable Interfaces

```python
def build_delivery_workbench(
    connection, *, report_date: date, today: date
) -> dict[str, object]: ...

def assert_delivery_allowed(
    connection,
    *,
    report_date: date,
    channel: str,
    today: date,
    confirm_uncertain: bool = False,
) -> None: ...
```

`build_delivery_workbench` 返回 `date`、`date_state`、`snapshot_available`、`article_available`、`stages` 和 `channels`。每个渠道包含 `channel`、`status`、`attempts`、`updated_at`、`error_code` 和 `actions`。

`assert_delivery_allowed` 对未来日期、缺失快照/文章包、成功、执行中和未确认的不确定状态抛出 `ValueError`；只有允许调用既有渠道服务时才返回。

---

### Task 1: Build the delivery workbench domain service

**Files:**
- Create: `src/jobflow/operations/delivery_workbench.py`
- Test: `tests/operations/test_delivery_workbench.py`

**Interfaces:**
- Consumes: 数据库连接、目标日期和显式传入的 `today`。
- Produces: `build_delivery_workbench()` 和 `assert_delivery_allowed()`。

- [ ] **Step 1: Write failing date tests**

创建 mocked connection，分别模拟未来日期无查询、历史日期有快照、历史日期无快照：

```python
def test_future_date_is_not_actionable():
    result = build_delivery_workbench(
        connection, report_date=date(2026, 9, 10), today=date(2026, 9, 9)
    )
    assert result["date_state"] == "future"
    assert result["snapshot_available"] is False
    assert result["channels"] == []


def test_past_date_reuses_existing_snapshot():
    result = build_delivery_workbench(
        connection, report_date=date(2026, 9, 8), today=date(2026, 9, 9)
    )
    assert result["date_state"] == "past"
    assert result["snapshot_available"] is True
```

- [ ] **Step 2: Verify the tests fail**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/operations/test_delivery_workbench.py
```

Expected: collection failure because the module does not exist.

- [ ] **Step 3: Implement the minimum read model**

Use parameterized SQL. Read whether the requested date has a successful snapshot/batch, the existing article status source, Telegram state from `ops.report_deliveries` and `ops.report_channel_deliveries`, and WeChat state from `ops.wechat_draft_jobs`. Normalize only these values:

```python
STATUS_ACTIONS = {
    "not_sent": ("send",),
    "sending": (),
    "creating": (),
    "sent": (),
    "created": (),
    "failed": ("retry",),
    "uncertain": (),
}
```

The read model indicates that `uncertain` requires confirmation but does not enable a retry itself.

- [ ] **Step 4: Add action-policy tests**

```python
@pytest.mark.parametrize(
    ("status", "allowed", "confirm"),
    [
        ("sent", False, False),
        ("failed", True, False),
        ("uncertain", False, False),
        ("uncertain", True, True),
    ],
)
def test_delivery_policy(status, allowed, confirm):
    if allowed:
        assert_delivery_allowed(
            connection,
            report_date=REPORT_DATE,
            channel="telegram",
            today=TODAY,
            confirm_uncertain=confirm,
        )
    else:
        with pytest.raises(ValueError):
            assert_delivery_allowed(
                connection,
                report_date=REPORT_DATE,
                channel="telegram",
                today=TODAY,
                confirm_uncertain=confirm,
            )
```

- [ ] **Step 5: Run and commit Task 1**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/operations/test_delivery_workbench.py
git add src/jobflow/operations/delivery_workbench.py tests/operations/test_delivery_workbench.py
git commit -m "增加按日期渠道投放状态服务"
```

Expected: all Task 1 tests pass; commit contains only the service and its test.

### Task 2: Expose a safe date-specific API contract

**Files:**
- Modify: `src/jobflow/api/dashboard.py`
- Modify: `src/jobflow/api/reports.py`
- Test: `tests/api/test_dashboard_deliveries.py`
- Test: `tests/api/test_reports.py`
- Test: `tests/api/test_wechat_reports.py`

**Interfaces:**
- Consumes: Task 1 interfaces.
- Produces: `GET /dashboard/workbench?report_date=YYYY-MM-DD` and guarded existing channel action routes.

- [ ] **Step 1: Add failing workbench endpoint tests**

```python
def test_workbench_returns_independent_channels(client):
    response = client.get("/dashboard/workbench?report_date=2026-09-08")
    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-09-08"
    assert {row["channel"] for row in payload["channels"]} == {"telegram", "wechat"}


def test_future_workbench_is_readable_but_not_actionable(client):
    response = client.get("/dashboard/workbench?report_date=2099-01-01")
    assert response.status_code == 200
    assert response.json()["date_state"] == "future"
    assert response.json()["channels"] == []
```

- [ ] **Step 2: Add failing action-guard tests**

For both Telegram and WeChat routes, override the sender/creator with a mock and assert it is not called for future, missing-snapshot, successful, sending, or unconfirmed uncertain states. Assert HTTP 409 and safe `detail` text.

```python
response = client.post(
    "/reports/daily/multi/send?snapshot_date=2026-09-08&confirm_uncertain=false",
    headers=ADMIN_HEADERS,
)
assert response.status_code == 409
sender.assert_not_called()
```

- [ ] **Step 3: Verify the API tests fail**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/api/test_dashboard_deliveries.py tests/api/test_reports.py tests/api/test_wechat_reports.py
```

Expected: missing workbench route and missing action guard failures.

- [ ] **Step 4: Implement the workbench route**

Import `build_delivery_workbench` in `api/dashboard.py` and return its safe dictionary. Keep the existing `/dashboard/deliveries` route for compatibility until callers migrate.

- [ ] **Step 5: Guard existing action routes**

Add `confirm_uncertain: bool = False` as a query parameter to Telegram and WeChat action handlers. Call `assert_delivery_allowed()` before the sender/creator and translate only policy `ValueError` to HTTP 409. Preserve current authentication and successful response shapes.

- [ ] **Step 6: Run and commit Task 2**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/api/test_dashboard_deliveries.py tests/api/test_reports.py tests/api/test_wechat_reports.py
git add src/jobflow/api/dashboard.py src/jobflow/api/reports.py tests/api/test_dashboard_deliveries.py tests/api/test_reports.py tests/api/test_wechat_reports.py
git commit -m "增加按日期投放工作台接口"
```

Expected: all selected API tests pass and no external sender is called by rejected requests.

### Task 3: Connect the Streamlit workbench UI

**Files:**
- Modify: `src/jobflow/dashboard/app.py`
- Modify: `src/jobflow/dashboard/components.py`
- Test: `tests/dashboard/test_dashboard_contract.py`

**Interfaces:**
- Consumes: Task 2 workbench and action endpoints.
- Produces: date selector, five-stage display, independent channel cards, guarded actions and post-action refresh.

- [ ] **Step 1: Add failing UI contract tests**

```python
def test_dashboard_contains_date_workbench_and_confirmation():
    app = Path("src/jobflow/dashboard/app.py").read_text(encoding="utf-8")
    assert "dashboard/workbench" in app
    assert "confirm_uncertain" in app
    assert "未来日期" in app
```

Also assert that no SQL statement or shell execution appears in the dashboard files.

- [ ] **Step 2: Verify the dashboard tests fail**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/dashboard/test_dashboard_contract.py
```

- [ ] **Step 3: Render the unified workbench**

Keep the existing sidebar and authentication. Replace `render_deliveries` with a localhost API read of `/dashboard/workbench`; render stages in order and one channel section per returned channel. The API's `actions` field is the only source of action availability.

```python
CHANNEL_LABELS = {"telegram": "Telegram", "wechat": "微信公众号草稿"}
ACTION_LABELS = {
    "send": "手动投放",
    "retry": "再次投放",
    "confirm_and_retry": "确认未收到后重试",
}
```

For `uncertain`, show a checkbox that states the administrator checked the external channel. Only send `confirm_uncertain=true` after it is checked. Future dates show “未到时间，无法抓取或投放” and no channel buttons.

- [ ] **Step 4: Refresh after an action**

After the API call returns, save the safe result in session state and call `st.rerun()`. Display safe status/error codes only; do not display raw exception strings or response URLs.

- [ ] **Step 5: Run and commit Task 3**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/dashboard/test_dashboard_contract.py
git add src/jobflow/dashboard/app.py src/jobflow/dashboard/components.py tests/dashboard/test_dashboard_contract.py
git commit -m "接入按日期渠道投放工作台"
```

Expected: all dashboard contract tests pass and the commit preserves pre-existing user edits in both dashboard files.

### Task 4: Verify and document deployment

**Files:**
- Modify: `docs/guides/ubuntu-deployment.md`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: repeatable local checks and a server acceptance path that does not trigger duplicate delivery.

- [ ] **Step 1: Run the focused suite**

```powershell
$env:PYTHONPATH='src'; python -m pytest -q `
  tests/operations/test_delivery_workbench.py `
  tests/api/test_dashboard_deliveries.py `
  tests/api/test_reports.py `
  tests/api/test_wechat_reports.py `
  tests/dashboard/test_dashboard_contract.py
```

Expected: all focused tests pass.

- [ ] **Step 2: Run repository checks**

```powershell
git diff --check
ruff check src tests
```

Expected: no whitespace errors and no Ruff findings.

- [ ] **Step 3: Add deployment and read-only acceptance commands**

Document these commands in `docs/guides/ubuntu-deployment.md`:

```bash
cd ~/services/jobflow
git pull --ff-only origin main
docker compose -f compose.yaml -f compose.proxy.yaml build api
docker compose -f compose.yaml -f compose.proxy.yaml up -d --no-deps --force-recreate api
curl --fail http://127.0.0.1:8000/ready
```

Then document a credential-protected `GET /dashboard/workbench?report_date=<existing-date>` check. Deployment validation must not call Telegram or WeChat write endpoints.

- [ ] **Step 4: Run manual UI acceptance**

Use one historical date with an existing snapshot and verify: both channel states display independently; successful channels have no ordinary retry; future dates are disabled; failed channels expose retry; uncertain channels require explicit confirmation. Do not create a second Telegram message or WeChat draft merely to test the button.

- [ ] **Step 5: Commit Task 4 documentation**

```bash
git add docs/guides/ubuntu-deployment.md
git commit -m "补充投放工作台验收步骤"
```

## Self-Review

- Spec coverage: Task 1 owns date/channel policy; Task 2 enforces it at the backend; Task 3 renders it; Task 4 verifies local and server behavior.
- Placeholder scan: no placeholder implementation decisions remain.
- Type consistency: both API routes consume the exact Task 1 signatures; UI consumes only the Task 2 response.
- YAGNI: service restart controls, full daily reruns, new tables, new dependencies and automatic WeChat publication remain outside this plan.
