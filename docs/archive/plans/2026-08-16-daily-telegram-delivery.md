# JobFlow V1.1 Daily Telegram Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在每日四城市抓取和 ETL 成功后自动发送固定规则中文 Telegram 报告，并使用 5 分钟 transient timer 完成一次真实端到端验收。

**Architecture:** 保留现有 `ops/daily_update.sh` 作为唯一编排入口，在 ETL 成功后通过正在运行的 API 容器调用 `POST /reports/cities/send?mode=query`。API 容器从自身环境读取 `REPORT_TRIGGER_TOKEN`，宿主机脚本和 journal 不记录实际 Token；Telegram 失败使 oneshot service 失败，但不回滚已经成功提交的 ETL。

**Tech Stack:** Bash、Docker Compose、Python 3 标准库 `urllib.request`、FastAPI、systemd service/timer、Telegram Bot API、PostgreSQL。

## Global Constraints

- 固定使用 `mode=query`，不调用 OpenAI 兼容服务/OpenAI，不将查询模板报告描述为真实 AI 生成。
- 不显示、记录或提交密码、OpenAI Key、Telegram Token、Chat ID、Cookie、Webhook、私钥或 `.env` 实际值。
- ETL 成功后 Telegram 失败：保留数据库更新，daily service 非零退出并标记失败。
- 只有报告接口返回 JSON 对象且 `status=sent`，Telegram 阶段才成功。
- 不修改正式 `jobflow-daily-update.timer` 的每天 `09:00 Asia/Shanghai` 计划。
- 五分钟测试使用独立 transient timer，测试前确认没有 daily service 正在运行。
- Windows 本机可以关机；Ubuntu 服务器、网络、Xvfb、Chrome、PostgreSQL、API 和 BOSS 登录态必须可用。
- 不自动绕过验证码或登录验证；登录失效时停止任务并保留旧快照。
- 不创建 Day 23 笔记。
- 不自动 commit 或 push；每个提交点只检查状态并等待用户明确授权。

---

## File Structure

### Ubuntu 服务器文件

- Modify: `<JOBFLOW_DIR>/ops/daily_update.sh` — 每日抓取、快照、ETL 和 Telegram 编排。
- Preserve: `<JOBFLOW_DIR>/ops/daily_update.sh.before-telegram` — 修改前的可回退备份。
- Verify: `/etc/systemd/system/jobflow-daily-update.service` — 现有 oneshot，不改变配置。
- Preserve: `/etc/systemd/system/jobflow-daily-update.timer` — 正式每天 09:00 timer，不修改。

### Windows 仓库文件

- Create: `ops/daily_update.sh` — 从真实验收后的 Ubuntu 脚本同步回仓库，作为 clone 用户的版本化来源。
- Create: `tests/ops/test_daily_update_script.py` — 静态验证发送顺序、query 模式和敏感值边界。
- Modify: `README.md` — 更新自动 Telegram 状态、五分钟验收和维护流程。
- Modify: `docs/guides/ubuntu-deployment.md` — 记录 service/timer、临时测试与日志验收。
- Modify: `docs/project-handoff.md` — 更新当前实际停点和未完成边界。
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\知识卡片\systemd Service 与 Timer 小白指南.md` — 记录 transient timer 和失败状态。
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\知识卡片\Telegram Bot 私聊推送.md` — 记录自动发送链路。
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\知识卡片\JobFlow V1.1 Ubuntu 每日自动更新小白指南.md` — 更新 V1.1 验收边界。
- Modify: `<PRIVATE_JOBFLOW_KB_ROOT>\每日记录\JobFlow Day 22 - OpenAI 兼容服务 报告与 Telegram 私聊推送.md` — 记录当天已完成工作，不创建未来笔记。

---

### Task 1: Add a Repository Contract Test for the Daily Script

**Files:**
- Create: `tests/ops/test_daily_update_script.py`
- Expected later: `ops/daily_update.sh`

**Interfaces:**
- Consumes: repository root resolved from `Path(__file__).parents[2]`.
- Produces: a static contract requiring ETL before query-mode Telegram delivery and forbidding host-side `.env` token extraction.

- [ ] **Step 1: Create the failing contract test**

Create `tests/ops/test_daily_update_script.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "daily_update.sh"


def read_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_daily_update_script_exists_and_is_strict() -> None:
    text = read_script()

    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -Eeuo pipefail" in text
    assert "flock -n 9" in text
    assert "scripts/boss_cdp_raw.py --check" in text


def test_daily_update_sends_query_report_after_etl() -> None:
    text = read_script()

    etl_position = text.index("docker compose run --rm etl")
    report_position = text.index("开始发送 Telegram 查询简报")

    assert etl_position < report_position
    assert "docker compose exec -T api python -" in text
    assert "/reports/cities/send?mode=query" in text
    assert 'payload.get("status") != "sent"' in text


def test_daily_update_does_not_extract_or_print_trigger_token_on_host() -> None:
    text = read_script()

    assert "sed -n 's/^REPORT_TRIGGER_TOKEN=" not in text
    assert "source .env" not in text
    assert "set -x" not in text
    assert "REPORT_TRIGGER_TOKEN_VALUE" not in text
```

- [ ] **Step 2: Run the test and verify the intended failure**

Run on Windows from `<LOCAL_JOBFLOW_DIR>`:

```powershell
conda run -n jobflow python -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: FAIL with `FileNotFoundError` because repository file `ops/daily_update.sh` does not exist yet. If `conda run` has the known temporary-file issue, run the `jobflow` environment Python executable directly.

- [ ] **Step 3: Inspect the failure boundary**

Run:

```powershell
git status --short --branch
git diff -- tests/ops/test_daily_update_script.py
```

Expected: only the new test appears for this task; no server file, `.env`, snapshot or credential is staged.

- [ ] **Step 4: Stop at the commit gate**

Do not commit. Record that the test is intentionally red and continue only with the user’s approval to perform the Ubuntu script edit.

---

### Task 2: Add Secure Query-Mode Telegram Delivery to the Ubuntu Script

**Files:**
- Modify: `<JOBFLOW_DIR>/ops/daily_update.sh`
- Create backup: `<JOBFLOW_DIR>/ops/daily_update.sh.before-telegram`

**Interfaces:**
- Consumes: running Compose `api` container with `REPORT_TRIGGER_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and endpoint `POST /reports/cities/send?mode=query`.
- Produces: `send_query_report()` Bash function; exit `0` only when response JSON contains `status=sent`, otherwise exit nonzero.

- [ ] **Step 1: Confirm preconditions without exposing secrets**

Run on Ubuntu:

```bash
cd <JOBFLOW_DIR>

systemctl is-active jobflow-xvfb.service
systemctl is-active jobflow-boss-chrome.service
systemctl is-active jobflow-daily-update.timer
systemctl is-active jobflow-daily-update.service || true
docker compose ps
curl --fail http://<SERVER_IP>:8000/ready
```

Expected: Xvfb, Chrome and timer are `active`; daily service is `inactive`; PostgreSQL and API are healthy; `/ready` succeeds.

- [ ] **Step 2: Create a recoverable server backup**

Run:

```bash
cp -p \
  <JOBFLOW_DIR>/ops/daily_update.sh \
  <JOBFLOW_DIR>/ops/daily_update.sh.before-telegram

ls -l \
  <JOBFLOW_DIR>/ops/daily_update.sh \
  <JOBFLOW_DIR>/ops/daily_update.sh.before-telegram
```

Expected: both files exist with executable permissions; do not print their full contents into chat.

- [ ] **Step 3: Add the secure report function**

Open:

```bash
nano <JOBFLOW_DIR>/ops/daily_update.sh
```

Insert the following function after the variable declarations and before the first runtime command:

```bash
send_query_report() {
    docker compose exec -T api python - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

token = os.getenv("REPORT_TRIGGER_TOKEN")
if not token:
    print("Telegram report failed: missing REPORT_TRIGGER_TOKEN", file=sys.stderr)
    raise SystemExit(1)

request = urllib.request.Request(
    "http://127.0.0.1:8000/reports/cities/send?mode=query",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    print(f"Telegram report failed: HTTP {exc.code}", file=sys.stderr)
    raise SystemExit(1) from None
except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
    print(f"Telegram report failed: {type(exc).__name__}", file=sys.stderr)
    raise SystemExit(1) from None

if not isinstance(payload, dict) or payload.get("status") != "sent":
    status = payload.get("status") if isinstance(payload, dict) else "invalid"
    print(f"Telegram report failed: status={status}", file=sys.stderr)
    raise SystemExit(1)

print(f"Telegram report sent: city_count={payload.get('city_count')}")
PY
}
```

This code reads the token only inside the API container. It never interpolates the actual value into the host command line or journal.

- [ ] **Step 4: Call the function only after ETL succeeds**

At the end of `daily_update.sh`, replace the existing final success line:

```bash
echo "JobFlow 每日更新完成"
```

with:

```bash
echo "开始发送 Telegram 查询简报"
send_query_report
echo "Telegram 查询简报发送完成"
echo "JobFlow 每日更新与 Telegram 推送完成"
```

The existing `set -Eeuo pipefail` makes a failed report call stop the script with nonzero status. Do not add `|| true` around `send_query_report`.

- [ ] **Step 5: Validate Bash syntax and ordering without sending**

Run:

```bash
bash -n <JOBFLOW_DIR>/ops/daily_update.sh

grep -n -E \
  'docker compose run --rm etl|开始发送 Telegram|send_query_report|mode=query|每日更新与 Telegram' \
  <JOBFLOW_DIR>/ops/daily_update.sh
```

Expected: `bash -n` is silent; ETL appears before the Telegram call; no actual Token value is printed.

- [ ] **Step 6: Verify rollback path is available**

Do not run this command now. Record the exact recovery command:

```bash
cp -p \
  <JOBFLOW_DIR>/ops/daily_update.sh.before-telegram \
  <JOBFLOW_DIR>/ops/daily_update.sh
```

Use it only if the new script cannot pass syntax validation or must be rolled back after failed diagnosis.

---

### Task 3: Schedule a Five-Minute Transient End-to-End Test

**Files:**
- No persistent project file changes.
- Runtime state: transient `jobflow-daily-update-test-<timestamp>.timer` and matching service.
- Runtime note: `/tmp/jobflow-daily-update-test-unit` stores only the transient unit name, never a secret.

**Interfaces:**
- Consumes: verified `jobflow-daily-update.service` and modified `daily_update.sh`.
- Produces: one trigger approximately five minutes later without modifying the formal 09:00 timer.

- [ ] **Step 1: Confirm the formal timer and idle service**

Run:

```bash
systemctl status jobflow-daily-update.timer --no-pager
systemctl is-active jobflow-daily-update.service || true
systemctl list-timers --all | grep jobflow
```

Expected: formal timer is `active (waiting)` with next 09:00 trigger; daily service is `inactive`.

- [ ] **Step 2: Create a unique transient timer for five minutes later**

Run:

```bash
TEST_UNIT="jobflow-daily-update-test-$(date +%Y%m%d-%H%M%S)"
printf '%s\n' "$TEST_UNIT" | tee /tmp/jobflow-daily-update-test-unit

sudo systemd-run \
  --unit="$TEST_UNIT" \
  --on-active=5m \
  --timer-property=AccuracySec=1s \
  /usr/bin/systemctl start jobflow-daily-update.service
```

Expected: output names a transient `.timer` and `.service`. It must not mention modification of `/etc/systemd/system/jobflow-daily-update.timer`.

- [ ] **Step 3: Verify the transient and formal timers side by side**

Run:

```bash
TEST_UNIT="$(cat /tmp/jobflow-daily-update-test-unit)"

systemctl status "${TEST_UNIT}.timer" --no-pager
systemctl list-timers --all | grep -E 'jobflow-daily-update(-test)?'
```

Expected: transient timer is waiting about five minutes; formal timer still shows the next 09:00 trigger.

- [ ] **Step 4: Wait without restarting Chrome or manually running the service**

Keep Ubuntu powered and online. Windows may remain on for observation but is not required for execution. Do not run `systemctl start jobflow-daily-update.service` manually during the countdown.

---

### Task 4: Verify Telegram Delivery and Failure Boundaries

**Files:**
- No code changes.
- Reads: systemd journal, PostgreSQL batch state, Telegram private chat.

**Interfaces:**
- Consumes: transient timer trigger and daily service output.
- Produces: evidence that scheduled execution completed ETL and Telegram delivery, or a precisely classified failure.

- [ ] **Step 1: Read the complete daily service journal after the trigger**

Run after the five-minute trigger finishes:

```bash
journalctl \
  -u jobflow-daily-update.service \
  --since '-20 minutes' \
  --no-pager
```

Expected success markers, in order:

```text
所有检查通过，可以开始抓取
BOSS 抓取环境检查通过
抓取完成：上海
抓取完成：北京
抓取完成：杭州
抓取完成：深圳
合并完成：60 条
ETL completed
开始发送 Telegram 查询简报
Telegram report sent: city_count=4
Telegram 查询简报发送完成
JobFlow 每日更新与 Telegram 推送完成
Deactivated successfully
```

- [ ] **Step 2: Verify systemd result**

Run:

```bash
systemctl status jobflow-daily-update.service --no-pager
```

Expected: oneshot is now `inactive (dead)` with recent successful completion. If it is `failed`, do not immediately rerun; inspect the journal first.

- [ ] **Step 3: Verify the latest database batch without secrets**

Run:

```bash
cd <JOBFLOW_DIR>

docker compose exec -T postgres \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT id, status, row_count FROM ops.batches ORDER BY id DESC LIMIT 1;" \
  -c "SELECT COUNT(*) AS raw_rows FROM raw.job_records WHERE batch_id = (SELECT MAX(id) FROM ops.batches);"'
```

Expected: latest batch is `succeeded`; `row_count` equals latest `raw_rows` and normally equals the four-city merged count.

- [ ] **Step 4: Verify the actual Telegram outcome**

Open the configured Telegram private chat and confirm a new Chinese city report arrived after the transient timer fired. The report must contain current city metrics, not merely an API `sent` response.

Do not share Bot Token, Chat ID or screenshots containing unrelated private messages.

- [ ] **Step 5: Classify failure without undoing ETL**

If Telegram did not arrive, use these boundaries:

```text
HTTP 401 → REPORT_TRIGGER_TOKEN missing or mismatched in API container
HTTP 502 → Telegram delivery failed
HTTP 503 → report or Telegram configuration unavailable
status=skipped → no city rows; business delivery failed
URLError / TimeoutError → API container request path unavailable
ETL succeeded + report failed → keep database, service remains failed
```

Do not rerun the full task until the failure layer is identified. If only delivery failed and the database is current, use the existing authenticated report endpoint to perform a report-only retry after fixing the cause.

- [ ] **Step 6: Confirm the formal timer remains unchanged**

Run:

```bash
systemctl status jobflow-daily-update.timer --no-pager
systemctl list-timers --all | grep jobflow-daily-update.timer
```

Expected: formal timer is still `enabled`, `active (waiting)`, and scheduled for the next 09:00 Asia/Shanghai run.

---

### Task 5: Clean Up the Transient Timer and Sync the Validated Script to Git

**Files:**
- Create: `ops/daily_update.sh`
- Modify: `README.md`
- Modify: `docs/guides/ubuntu-deployment.md`
- Modify: `docs/project-handoff.md`
- Modify relevant Obsidian cards listed in File Structure.

**Interfaces:**
- Consumes: server script that passed the five-minute real Telegram test.
- Produces: repository-managed deployment script and documentation matching actual server behavior.

- [ ] **Step 1: Remove remaining transient runtime state**

Run on Ubuntu:

```bash
TEST_UNIT="$(cat /tmp/jobflow-daily-update-test-unit)"

sudo systemctl stop "${TEST_UNIT}.timer" 2>/dev/null || true
sudo systemctl reset-failed "${TEST_UNIT}.service" 2>/dev/null || true
sudo systemctl daemon-reload

systemctl list-timers --all | grep jobflow
```

Expected: no future transient test trigger remains; formal 09:00 timer remains.

- [ ] **Step 2: Copy the validated, non-secret script back to Windows**

From Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force <LOCAL_JOBFLOW_DIR>\ops | Out-Null

scp `
  <SSH_USER>@<SERVER_IP>:<JOBFLOW_DIR>/ops/daily_update.sh `
<LOCAL_JOBFLOW_DIR>\ops\daily_update.sh
```

Expected: `<LOCAL_JOBFLOW_DIR>\ops\daily_update.sh` exists. Do not copy `.env`, Profile, snapshot, lock file or the server backup into Git.

- [ ] **Step 3: Run the repository contract test**

Run from `<LOCAL_JOBFLOW_DIR>`:

```powershell
conda run -n jobflow python -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: `3 passed`. If `conda run` fails for the known environment reason, run the environment’s Python executable directly.

- [ ] **Step 4: Run existing report and Telegram tests**

Run:

```powershell
conda run -n jobflow python -m pytest `
  tests/api/test_reports.py `
  tests/reports/test_service.py `
  tests/channels/test_telegram.py `
  -q
```

Expected: all selected tests pass. These tests use mocks and must not send another real Telegram message.

- [ ] **Step 5: Update README, deployment, handoff and knowledge notes**

Document only the measured result:

```text
Five-minute transient timer triggered successfully
Four-city ETL completed
Query-mode Telegram report returned status=sent
Telegram private chat received the report
Formal 09:00 timer remained enabled and waiting
```

If any item failed, document it as pending or failed rather than completed. Include the report retry procedure and the fact that Windows can be off while Ubuntu runs.

- [ ] **Step 6: Validate documentation and repository hygiene**

Run:

```powershell
git diff --check
git status --short --branch
git diff -- README.md docs/guides/ubuntu-deployment.md docs/project-handoff.md ops/daily_update.sh tests/ops/test_daily_update_script.py
```

Expected: no `.env`, snapshot, Profile, Token, Chat ID, password or server backup appears. Existing unrelated user changes remain untouched.

- [ ] **Step 7: Stop at the commit and push gate**

Do not run `git add`, `git commit` or `git push`. Report the exact changed files, test results, real Telegram evidence and formal timer state, then wait for explicit user authorization.

---

## Completion Criteria

This implementation is complete only when all are true:

- `daily_update.sh` calls the query-mode report endpoint after ETL;
- actual Token values never appear in the host script, command history, journal, docs or Git;
- Telegram failure makes daily service fail without rolling back ETL;
- transient timer fires about five minutes after creation;
- four-city ETL succeeds;
- endpoint returns `status=sent`;
- the user confirms the Telegram private chat received the new Chinese report;
- formal daily timer remains scheduled for 09:00 Asia/Shanghai;
- validated script is synced into repository `ops/daily_update.sh`;
- tests and documentation checks pass;
- no commit or push occurs without explicit authorization.
