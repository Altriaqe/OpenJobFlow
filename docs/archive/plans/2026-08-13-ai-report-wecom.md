# AI City Report and WeCom Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a protected HTTP endpoint that reads the existing city aggregate, generates a fact-constrained Chinese report with the OpenAI Responses API, and sends it to an enterprise WeChat group robot.

**Architecture:** Keep OpenAI generation, WeCom delivery, report orchestration, and HTTP authentication in separate modules. External calls are injected in tests, while production configuration comes only from environment variables; the ETL transaction boundary and existing analytics query remain unchanged.

**Tech Stack:** Python 3.12, FastAPI, OpenAI Python SDK, Requests, psycopg 3, pytest, Ruff, PostgreSQL 18, Windows CMD.

## Global Constraints

- Use `POST /reports/cities/send` with `Authorization: Bearer <REPORT_TRIGGER_TOKEN>`.
- Read `OPENAI_API_KEY`, `OPENAI_MODEL`, `WECOM_WEBHOOK_URL`, and `REPORT_TRIGGER_TOKEN` only from environment variables.
- Use the OpenAI Responses API and read generated text from `response.output_text`.
- Send only city, job count, and metric scope to OpenAI; prohibit invented salary, trend, skill, and causal claims.
- Return `401` before database, OpenAI, or WeCom work when the token is absent or wrong.
- Return `200 skipped` for empty city data, `503` for database/OpenAI/configuration failure, and `502` for WeCom delivery failure.
- Do not expose secrets, SQL, Webhook URLs, or internal stack traces in API responses or logs.
- Automated tests must not call real OpenAI or WeCom services.
- Do not alter the ETL Worker transaction boundary or expose `raw` and individual job data.
- Do not run `git push` automatically.

---

### Task 1: Generate a fact-constrained city report with OpenAI

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `src/jobflow/ai/__init__.py`
- Create: `src/jobflow/ai/openai_summary.py`
- Create: `tests/ai/__init__.py`
- Create: `tests/ai/test_openai_summary.py`

**Interfaces:**
- Consumes: `rows: list[dict[str, object]]`, optional OpenAI client, and `OPENAI_MODEL`.
- Produces: `generate_city_report(rows, client=None, model=None) -> str`.
- Raises: `OpenAIConfigurationError` for missing model configuration and `OpenAISummaryError` for failed or empty model output.

- [ ] **Step 1: Add the OpenAI SDK and environment variable names**

Add to `[project].dependencies` in `pyproject.toml`:

```toml
"openai>=1.68,<2",
```

Append these non-secret example values to `.env.example`:

```dotenv
OPENAI_API_KEY=replace_with_an_openai_api_key
OPENAI_MODEL=replace_with_an_available_text_model
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=replace_me
REPORT_TRIGGER_TOKEN=replace_with_a_long_random_token
```

Install in the project environment:

```cmd
python -m pip install -e ".[dev]"
```

Expected: the editable project installs in Python 3.12 and `python -c "import openai"` exits successfully.

- [ ] **Step 2: Write the failing OpenAI tests**

Create package marker files `src/jobflow/ai/__init__.py` and `tests/ai/__init__.py`, then create `tests/ai/test_openai_summary.py`:

```python
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jobflow.ai.openai_summary import (
    OpenAIConfigurationError,
    OpenAISummaryError,
    generate_city_report,
)


def test_generate_city_report_uses_only_aggregate_facts():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text="城市岗位报告")
    rows = [
        {"city": "Hangzhou", "job_count": 12},
        {"city": "Lanzhou", "job_count": 8},
    ]

    result = generate_city_report(rows, client=client, model="test-model")

    assert result == "城市岗位报告"
    call = client.responses.create.call_args.kwargs
    assert call["model"] == "test-model"
    assert "Hangzhou" in call["input"]
    assert "12" in call["input"]
    assert "Lanzhou" in call["input"]
    assert "8" in call["input"]
    assert "当前数据库" in call["instructions"]
    assert "不得编造" in call["instructions"]


def test_generate_city_report_requires_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(OpenAIConfigurationError, match="OPENAI_MODEL"):
        generate_city_report([{"city": "Hangzhou", "job_count": 12}], client=Mock())


def test_generate_city_report_rejects_empty_output():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text="   ")

    with pytest.raises(OpenAISummaryError, match="empty output"):
        generate_city_report(
            [{"city": "Hangzhou", "job_count": 12}],
            client=client,
            model="test-model",
        )


def test_generate_city_report_hides_provider_error():
    client = Mock()
    client.responses.create.side_effect = RuntimeError("secret provider detail")

    with pytest.raises(OpenAISummaryError, match="OpenAI request failed") as exc_info:
        generate_city_report(
            [{"city": "Hangzhou", "job_count": 12}],
            client=client,
            model="test-model",
        )

    assert "secret provider detail" not in str(exc_info.value)
```

Run:

```cmd
pytest tests\ai\test_openai_summary.py -q
```

Expected: test collection fails because `jobflow.ai.openai_summary` does not exist.

- [ ] **Step 3: Implement the OpenAI adapter**

Create `src/jobflow/ai/openai_summary.py`:

```python
import json
import os

from openai import OpenAI


class OpenAIConfigurationError(Exception):
    pass


class OpenAISummaryError(Exception):
    pass


INSTRUCTIONS = """你是 JobFlow 招聘数据报告助手。
只根据输入的城市和岗位数量总结事实。
统计口径是当前数据库中的岗位数量，不代表历史趋势或完整市场规模。
不得编造薪资、技能、趋势、原因或输入中不存在的数字。
使用简洁中文输出适合企业微信群阅读的报告。"""


def generate_city_report(
    rows: list[dict[str, object]],
    *,
    client=None,
    model: str | None = None,
) -> str:
    selected_model = model or os.getenv("OPENAI_MODEL")
    if not selected_model:
        raise OpenAIConfigurationError("missing OPENAI_MODEL")

    openai_client = client or OpenAI()
    input_text = json.dumps(
        {"metric_scope": "当前数据库中的城市岗位数量", "cities": rows},
        ensure_ascii=False,
    )

    try:
        response = openai_client.responses.create(
            model=selected_model,
            instructions=INSTRUCTIONS,
            input=input_text,
        )
    except Exception as exc:
        raise OpenAISummaryError("OpenAI request failed") from exc

    report = response.output_text.strip()
    if not report:
        raise OpenAISummaryError("OpenAI returned empty output")

    return report
```

- [ ] **Step 4: Verify and commit Task 1**

```cmd
pytest tests\ai\test_openai_summary.py -q
ruff check src\jobflow\ai tests\ai
ruff format --check src\jobflow\ai tests\ai
git diff --check
git add pyproject.toml .env.example src\jobflow\ai tests\ai
git diff --cached --check
git commit -m "feat: 添加 OpenAI 城市岗位报告生成"
```

Expected: `4 passed`, Ruff and formatting pass, and no real API Key is staged.

---

### Task 2: Send reports through a WeCom robot and orchestrate the workflow

**Files:**
- Create: `src/jobflow/channels/__init__.py`
- Create: `src/jobflow/channels/wecom.py`
- Create: `src/jobflow/reports/__init__.py`
- Create: `src/jobflow/reports/service.py`
- Create: `tests/channels/__init__.py`
- Create: `tests/channels/test_wecom.py`
- Create: `tests/reports/__init__.py`
- Create: `tests/reports/test_service.py`

**Interfaces:**
- Produces: `send_wecom_text(report, webhook_url=None, post=None) -> None`.
- Produces: `send_city_report(connection, summary_generator=..., sender=...) -> dict[str, object]`.
- Raises: `WeComConfigurationError`, `WeComDeliveryError`, and existing OpenAI adapter errors.

- [ ] **Step 1: Write failing WeCom and orchestration tests**

Create the four empty package markers, then create `tests/channels/test_wecom.py`:

```python
from unittest.mock import Mock

import pytest

from jobflow.channels.wecom import (
    WeComConfigurationError,
    WeComDeliveryError,
    send_wecom_text,
)


def test_send_wecom_text_posts_expected_payload():
    response = Mock(status_code=200)
    response.json.return_value = {"errcode": 0, "errmsg": "ok"}
    post = Mock(return_value=response)

    send_wecom_text("城市岗位报告", webhook_url="https://example.test/hook", post=post)

    post.assert_called_once_with(
        "https://example.test/hook",
        json={"msgtype": "text", "text": {"content": "城市岗位报告"}},
        timeout=10,
    )


def test_send_wecom_text_requires_webhook(monkeypatch):
    monkeypatch.delenv("WECOM_WEBHOOK_URL", raising=False)

    with pytest.raises(WeComConfigurationError, match="WECOM_WEBHOOK_URL"):
        send_wecom_text("report", post=Mock())


def test_send_wecom_text_rejects_wecom_error_without_exposing_webhook():
    response = Mock(status_code=200)
    response.json.return_value = {"errcode": 93000, "errmsg": "invalid webhook"}
    post = Mock(return_value=response)

    with pytest.raises(WeComDeliveryError, match="WeCom rejected message") as exc_info:
        send_wecom_text("report", webhook_url="https://secret.example/hook", post=post)

    assert "secret.example" not in str(exc_info.value)
```

Create `tests/reports/test_service.py`:

```python
from unittest.mock import Mock

import pytest

from jobflow.ai.openai_summary import OpenAISummaryError
from jobflow.reports.service import send_city_report


def connection_with_rows(rows):
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = rows
    return connection


def test_send_city_report_skips_external_calls_for_empty_data():
    summary_generator = Mock()
    sender = Mock()

    result = send_city_report(
        connection_with_rows([]),
        summary_generator=summary_generator,
        sender=sender,
    )

    assert result == {"status": "skipped", "city_count": 0}
    summary_generator.assert_not_called()
    sender.assert_not_called()


def test_send_city_report_generates_and_sends_report():
    rows = [{"city": "Hangzhou", "job_count": 12}]
    summary_generator = Mock(return_value="城市岗位报告")
    sender = Mock()

    result = send_city_report(
        connection_with_rows([("Hangzhou", 12)]),
        summary_generator=summary_generator,
        sender=sender,
    )

    summary_generator.assert_called_once_with(rows)
    sender.assert_called_once_with("城市岗位报告")
    assert result == {"status": "sent", "city_count": 1}


def test_send_city_report_does_not_send_when_openai_fails():
    summary_generator = Mock(side_effect=OpenAISummaryError("OpenAI request failed"))
    sender = Mock()

    with pytest.raises(OpenAISummaryError):
        send_city_report(
            connection_with_rows([("Hangzhou", 12)]),
            summary_generator=summary_generator,
            sender=sender,
        )

    sender.assert_not_called()
```

Run:

```cmd
pytest tests\channels\test_wecom.py tests\reports\test_service.py -q
```

Expected: collection fails because the channel and report modules do not exist.

- [ ] **Step 2: Implement the WeCom adapter**

Create `src/jobflow/channels/wecom.py`:

```python
import os

import requests


class WeComConfigurationError(Exception):
    pass


class WeComDeliveryError(Exception):
    pass


def send_wecom_text(
    report: str,
    *,
    webhook_url: str | None = None,
    post=None,
) -> None:
    selected_webhook = webhook_url or os.getenv("WECOM_WEBHOOK_URL")
    if not selected_webhook:
        raise WeComConfigurationError("missing WECOM_WEBHOOK_URL")

    post_request = post or requests.post
    try:
        response = post_request(
            selected_webhook,
            json={"msgtype": "text", "text": {"content": report}},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise WeComDeliveryError("WeCom request failed") from exc

    if payload.get("errcode") != 0:
        raise WeComDeliveryError("WeCom rejected message")
```

- [ ] **Step 3: Implement report orchestration**

Create `src/jobflow/reports/service.py`:

```python
from jobflow.ai.openai_summary import generate_city_report
from jobflow.channels.wecom import send_wecom_text
from jobflow.db.analytics import list_city_job_counts


def send_city_report(
    connection,
    *,
    summary_generator=generate_city_report,
    sender=send_wecom_text,
) -> dict[str, object]:
    rows = list_city_job_counts(connection, limit=100)
    if not rows:
        return {"status": "skipped", "city_count": 0}

    report = summary_generator(rows)
    sender(report)
    return {"status": "sent", "city_count": len(rows)}
```

Create empty package markers `src/jobflow/channels/__init__.py` and `src/jobflow/reports/__init__.py`.

- [ ] **Step 4: Verify and commit Task 2**

```cmd
pytest tests\channels\test_wecom.py tests\reports\test_service.py -q
ruff check src\jobflow\channels src\jobflow\reports tests\channels tests\reports
ruff format --check src\jobflow\channels src\jobflow\reports tests\channels tests\reports
git diff --check
git add src\jobflow\channels src\jobflow\reports tests\channels tests\reports
git diff --cached --check
git commit -m "feat: 添加企业微信报告发送服务"
```

Expected: `6 passed`, external services are never called, and checks pass.

---

### Task 3: Expose the protected report endpoint

**Files:**
- Create: `src/jobflow/api/reports.py`
- Modify: `src/jobflow/api/app.py`
- Create: `tests/api/test_reports.py`

**Interfaces:**
- Consumes: `get_connection`, `send_city_report`, and `REPORT_TRIGGER_TOKEN`.
- Produces: `POST /reports/cities/send` with Bearer authentication.

- [ ] **Step 1: Write failing API tests**

Create `tests/api/test_reports.py`:

```python
from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app
from jobflow.api.reports import get_report_sender


def report_client(monkeypatch, sender):
    monkeypatch.setenv("REPORT_TRIGGER_TOKEN", "test-trigger-token")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: Mock()
    app.dependency_overrides[get_report_sender] = lambda: sender
    return TestClient(app), app


def test_report_endpoint_rejects_missing_token_before_service(monkeypatch):
    sender = Mock()
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post("/reports/cities/send")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    sender.assert_not_called()


def test_report_endpoint_rejects_wrong_token_before_service(monkeypatch):
    sender = Mock()
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer wrong-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    sender.assert_not_called()


def test_report_endpoint_sends_with_correct_token(monkeypatch):
    sender = Mock(return_value={"status": "sent", "city_count": 2})
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "sent", "city_count": 2}
    sender.assert_called_once()


def test_report_endpoint_maps_wecom_failure_to_502(monkeypatch):
    from jobflow.channels.wecom import WeComDeliveryError

    sender = Mock(side_effect=WeComDeliveryError("WeCom request failed"))
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "report delivery failed"}


def test_report_endpoint_maps_openai_failure_to_503(monkeypatch):
    from jobflow.ai.openai_summary import OpenAISummaryError

    sender = Mock(side_effect=OpenAISummaryError("OpenAI request failed"))
    client, app = report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/cities/send",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "report service unavailable"}
```

Run:

```cmd
pytest tests\api\test_reports.py -q
```

Expected: collection fails because `jobflow.api.reports` does not exist.

- [ ] **Step 2: Implement authentication and error mapping**

Create `src/jobflow/api/reports.py`:

```python
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jobflow.ai.openai_summary import OpenAIConfigurationError, OpenAISummaryError
from jobflow.api.analytics import get_connection
from jobflow.channels.wecom import WeComConfigurationError, WeComDeliveryError
from jobflow.reports.service import send_city_report

router = APIRouter(prefix="/reports")
bearer = HTTPBearer(auto_error=False)


def get_report_sender():
    return send_city_report


def require_report_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:
    expected = os.getenv("REPORT_TRIGGER_TOKEN")
    provided = credentials.credentials if credentials else ""
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid report trigger token")


@router.post("/cities/send", dependencies=[Depends(require_report_token)])
def send_cities_report(
    connection=Depends(get_connection),
    report_sender=Depends(get_report_sender),
):
    try:
        return report_sender(connection)
    except WeComDeliveryError as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except (
        OpenAIConfigurationError,
        OpenAISummaryError,
        WeComConfigurationError,
    ) as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
```

Register the router in `src/jobflow/api/app.py`:

```python
from jobflow.api.reports import router as reports_router
```

Inside `create_app()` add:

```python
app.include_router(reports_router)
```

- [ ] **Step 3: Verify all automated behavior**

```cmd
pytest tests\api\test_reports.py -q
pytest -q
ruff check .
ruff format --check .
git diff --check
```

Expected: the five report API tests pass, the full suite increases from `61` to `76 passed`, and all quality checks pass. The existing third-party Starlette warning may remain.

- [ ] **Step 4: Commit Task 3 and the approved design documents**

```cmd
git add src\jobflow\api\reports.py src\jobflow\api\app.py tests\api\test_reports.py
git diff --cached --check
git commit -m "feat: 添加受保护的 AI 报告发送接口"
git add docs\superpowers\specs\2026-08-13-ai-report-wecom-design.md docs\superpowers\plans\2026-08-13-ai-report-wecom.md
git diff --cached --check
git commit -m "docs: 添加 AI 企业微信报告设计与计划"
git status --short --branch
```

Expected: both commits succeed, the worktree is clean, and no secret value is tracked. Do not push automatically.

---

## Manual Acceptance After Automated Tests

Create a dedicated enterprise WeChat test group and add a group robot. Configure the four real variables only in the local ignored `.env`, start PostgreSQL and Uvicorn, then call the endpoint once with the Bearer token. Verify exactly one fact-constrained report appears in the test group. Do not paste or screenshot secrets into chat, Git, logs, or documentation.
