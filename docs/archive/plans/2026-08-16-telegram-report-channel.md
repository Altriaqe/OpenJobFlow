# Telegram Report Channel Implementation Plan

> **For agentic workers:** Follow this plan task-by-task with a review checkpoint after each task. Do not commit or push without explicit user authorization.

**Goal:** Keep `POST /reports/cities/send` and its Bearer protection, but send the generated JobFlow city report to the user's Telegram private chat through the Telegram Bot API.

**Architecture:** Add a focused `telegram` channel adapter that sends `sendMessage` requests and raises configuration/delivery errors without exposing secrets. Keep report orchestration and API routing stable, switch the default sender from WeCom to Telegram, and pass the already-required HTTP/HTTPS proxy into runtime containers through Compose interpolation rather than storing proxy values in application code.

**Tech Stack:** Python 3.12, `requests`, FastAPI, pytest, Docker Compose v2+, Telegram Bot API.

## Global Constraints

- Keep `POST /reports/cities/send` and `Authorization: Bearer <REPORT_TRIGGER_TOKEN>` unchanged.
- Keep OpenAI 兼容服务/OpenAI-compatible report generation unchanged.
- Use `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the server `.env`; never print their values.
- Keep `.env` permissions at `600`; do not put proxy values in Python source or committed secrets.
- Do not implement personal-WeChat UI automation.
- Do not auto-commit or push; commits in the examples are optional checkpoints requiring user authorization.
- A real integration is complete only after the user's Telegram private chat receives both a direct test message and a report generated from current database data.

---

### Task 1: Build and unit-test the Telegram channel adapter

**Files:**
- Create: `src/jobflow/channels/telegram.py`
- Create: `tests/channels/test_telegram.py`
- Inspect: `src/jobflow/channels/wecom.py` for the existing adapter/error pattern

**Interfaces:**
- Produces `TelegramConfigurationError`, `TelegramDeliveryError`, and `send_telegram_text(report: str, *, bot_token: str | None = None, chat_id: str | None = None, post=None) -> None`.
- The injected `post` callable must receive `url`, `json`, and `timeout=10`, matching the existing WeCom test seam.
- A successful Telegram response has JSON `{"ok": true}`; any missing/false `ok` is a delivery failure.

- [ ] **Step 1: Write failing tests for the adapter contract**

Add tests with `Mock` responses for:

```python
def test_send_telegram_text_posts_expected_payload():
    response = Mock(status_code=200)
    response.json.return_value = {"ok": True, "result": {"message_id": 1}}
    post = Mock(return_value=response)

    send_telegram_text(
        "城市岗位报告",
        bot_token="bot-token",
        chat_id="12345",
        post=post,
    )

    post.assert_called_once_with(
        "https://api.telegram.org/botbot-token/sendMessage",
        json={"chat_id": "12345", "text": "城市岗位报告"},
        timeout=10,
    )
```

Also add tests that missing either configuration raises `TelegramConfigurationError`, an injected request exception raises `TelegramDeliveryError` without including the token, and a JSON response with `ok=False` raises `TelegramDeliveryError` without exposing the response payload.

- [ ] **Step 2: Run only the new tests and verify they fail**

Run:

```cmd
conda run -n jobflow pytest -q tests/channels/test_telegram.py
```

Expected: collection or test failures because `jobflow.channels.telegram` does not exist yet.

- [ ] **Step 3: Implement the minimal adapter**

Read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` with `os.getenv()` only when explicit keyword arguments are absent. Build the URL from the token, send the exact JSON payload above, call `raise_for_status()`, parse JSON, and require `payload.get("ok") is True`. Wrap all request/HTTP/JSON failures in `TelegramDeliveryError("Telegram request failed")`; use configuration-specific messages that mention only the missing variable name.

- [ ] **Step 4: Run the focused tests and lint**

Run:

```cmd
conda run -n jobflow pytest -q tests/channels/test_telegram.py
conda run -n jobflow ruff check src/jobflow/channels/telegram.py tests/channels/test_telegram.py
```

Expected: all focused tests pass and Ruff exits successfully.

- [ ] **Step 5: Stop for review**

Report the focused test result and wait for review. Do not commit unless the user explicitly authorizes it.

### Task 2: Wire Telegram into report orchestration and API error mapping

**Files:**
- Modify: `src/jobflow/reports/service.py`
- Modify: `src/jobflow/api/reports.py`
- Modify: `tests/reports/test_service.py`
- Modify: `tests/api/test_reports.py`

**Interfaces:**
- `send_city_report(..., sender=send_telegram_text)` remains the same public function shape and still returns `{"status": "skipped", "city_count": 0}` or `{"status": "sent", "city_count": n}`.
- `api.reports` catches `TelegramConfigurationError` with existing service-unavailable behavior (`503`) and `TelegramDeliveryError` with existing delivery-failed behavior (`502`).

- [ ] **Step 1: Change tests to assert Telegram is the default sender**

Keep the existing injected-sender tests. Add a test that imports `send_city_report` and verifies a normal one-row call uses the Telegram default when no sender override is passed, using monkeypatching or a patched module-level `send_telegram_text` so no network occurs. Replace the endpoint's WeCom failure mapping test with a Telegram delivery failure mapping test; add a Telegram configuration failure mapping test returning `503`.

- [ ] **Step 2: Run the focused orchestration/API tests and verify the expected failure**

Run:

```cmd
conda run -n jobflow pytest -q tests/reports/test_service.py tests/api/test_reports.py
```

Expected: the new default-sender or Telegram error tests fail while existing token and empty-data tests continue to pass.

- [ ] **Step 3: Wire the minimal production changes**

Import `send_telegram_text` in `reports/service.py` and use it as the default `sender`. Import `TelegramConfigurationError` and `TelegramDeliveryError` in `api/reports.py`; map them to the same generic response details currently used for the corresponding WeCom categories. Do not expose exception strings to clients.

- [ ] **Step 4: Run all affected tests**

Run:

```cmd
conda run -n jobflow pytest -q tests/channels/test_telegram.py tests/reports/test_service.py tests/api/test_reports.py
```

Expected: all affected tests pass.

- [ ] **Step 5: Stop for review**

Report test output and wait for review. Do not commit automatically.

### Task 3: Make the proxy available to runtime containers and update project docs

**Files:**
- Modify: `compose.yaml`
- Modify: `docs/project-handoff.md`
- Modify: `README.md`
- Modify: `docs/guides/ubuntu-deployment.md`
- Modify: `docs/reference/architecture.md`

**Interfaces:**
- Compose accepts `JOBFLOW_HTTP_PROXY`, `JOBFLOW_HTTPS_PROXY`, and `JOBFLOW_NO_PROXY` from the shell environment and passes them to `api` and one-shot `etl`/tool containers without hard-coding a secret.
- Application configuration documents `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; the old WeCom variables are marked inactive for the Telegram path.

- [ ] **Step 1: Add a Compose runtime-proxy testable configuration**

In the shared `x-jobflow-app.environment` block, add:

```yaml
      HTTP_PROXY: ${JOBFLOW_HTTP_PROXY:-}
      HTTPS_PROXY: ${JOBFLOW_HTTPS_PROXY:-}
      NO_PROXY: ${JOBFLOW_NO_PROXY:-postgres,localhost,127.0.0.1}
```

Do not put the proxy URL in `compose.yaml`; the value must come from the server shell environment.

- [ ] **Step 2: Document the Telegram configuration and safe Ubuntu command sequence**

Document the variable names only, never actual values. Include the runtime setup pattern:

```bash
export JOBFLOW_HTTP_PROXY=http://<PROXY_HOST>:<PROXY_PORT>
export JOBFLOW_HTTPS_PROXY=http://<PROXY_HOST>:<PROXY_PORT>
export JOBFLOW_NO_PROXY=postgres,localhost,127.0.0.1
docker compose up -d postgres api
```

Explain that `docker compose run -e ...` is for one-off tests, while the exported variables are required when recreating the long-running API container.

- [ ] **Step 3: Run configuration and quality checks**

Run:

```cmd
conda run -n jobflow pytest -q
conda run -n jobflow ruff check .
conda run -n jobflow ruff format --check .
```

Expected: the full Windows suite and both Ruff checks pass; no secret values appear in the diff.

- [ ] **Step 4: Stop for review**

Review the Compose diff carefully because it changes runtime networking. Do not commit or push automatically.

### Task 4: Configure Telegram on Ubuntu and perform real delivery acceptance

**Files:**
- Server-only `.env` at `<JOBFLOW_DIR>/.env` (never commit)
- No source changes in this task

**Interfaces:**
- Server `.env` contains `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` with values hidden from chat output.
- Running API receives proxy variables and can reach both OpenAI 兼容服务 and Telegram.

- [ ] **Step 1: Add the Bot Token without displaying it**

On Ubuntu, edit `.env` with `nano` and add `TELEGRAM_BOT_TOKEN=<real token>`. Keep the token only on the server and verify only with:

```bash
grep -E '^TELEGRAM_BOT_TOKEN=' .env | sed 's/=.*/=<已隐藏>/'
stat -c '%a %n' .env
```

Expected: the variable name is shown, the value is hidden, and permissions are `600 .env`.

- [ ] **Step 2: Retrieve the private Chat ID without printing the token**

After `/start` has been sent to the Bot, run a one-shot container command with the temporary proxy and print only update chat IDs:

```bash
docker compose run --rm \
  -e HTTP_PROXY="$JOBFLOW_HTTP_PROXY" \
  -e HTTPS_PROXY="$JOBFLOW_HTTPS_PROXY" \
  api python -c 'import os,requests; data=requests.get("https://api.telegram.org/bot"+os.environ["TELEGRAM_BOT_TOKEN"]+"/getUpdates", timeout=15).json(); print([u["message"]["chat"]["id"] for u in data.get("result", []) if "message" in u and "chat" in u["message"]])'
```

Copy the numeric ID into `TELEGRAM_CHAT_ID` in `.env`; never paste the token or the full `getUpdates` response into chat. Verify the variable name with the same masking pattern.

- [ ] **Step 3: Rebuild and recreate the API with runtime proxy variables**

Run from the project directory:

```bash
docker compose build api
docker compose up -d api
docker compose ps
```

Expected: the API container is `Up ... (healthy)` and the existing PostgreSQL data remains intact.

- [ ] **Step 4: Send a direct Telegram smoke-test message**

Use a one-shot command that imports `send_telegram_text` and sends a fixed, non-sensitive text. The command must include the runtime proxy variables, but must not echo the Bot Token:

```bash
docker compose run --rm \
  -e HTTP_PROXY="$JOBFLOW_HTTP_PROXY" \
  -e HTTPS_PROXY="$JOBFLOW_HTTPS_PROXY" \
  api python -c 'from jobflow.channels.telegram import send_telegram_text; send_telegram_text("JobFlow Telegram 通道测试")'
```

Expected: command exits successfully and the user receives the test message in the private chat.

- [ ] **Step 5: Trigger the complete protected report endpoint**

From a trusted client, call the existing API with the real trigger token kept out of chat history:

```bash
curl --fail -X POST \
  -H "Authorization: Bearer <REPORT_TRIGGER_TOKEN>" \
  http://<SERVER_IP>:8000/reports/cities/send
```

Expected: HTTP success with `status=sent` and the current city count, followed by the generated report arriving in the Telegram private chat.

- [ ] **Step 6: Record evidence and stop**

Record only non-secret evidence: Git commit, test counts, API status, returned city count, and confirmation that the private chat received both messages. Do not record Bot Token, Chat ID, proxy credentials, or the report trigger token. Do not claim Telegram integration complete unless both real messages were received.
