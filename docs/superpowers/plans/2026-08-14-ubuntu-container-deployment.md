# JobFlow Ubuntu Container Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one reusable JobFlow image, run snapshot ETL manually, expose a database-aware FastAPI service on the Ubuntu LAN, and verify the existing 30-job snapshot end to end.

**Architecture:** One Python 3.12 image is shared by the `etl` and `api` Compose services. PostgreSQL remains private, migrations and ETL run as explicit one-shot services, and the API exposes separate liveness and readiness endpoints.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3, pytest, Docker Engine 29, Docker Compose 1.29.2, PostgreSQL 18 Alpine, Ubuntu 22.04, UFW

## Global Constraints

- Keep PostgreSQL bound to `127.0.0.1`; never expose port 5432 to the LAN or internet.
- Expose FastAPI on port `8000` only to `<LAN_CIDR>` through UFW.
- Keep `.env`, BOSS snapshots, passwords, OpenAI keys, Webhooks, Tokens, Cookies, and private keys out of Git and image layers.
- Keep ETL manual; it must not run when the API or Ubuntu host starts.
- Exclude OpenAI reports, WeCom delivery, Caddy, DNS, TLS, authentication, and scheduling from this plan.
- Preserve every existing uncommitted AI/WeCom change; stage or commit nothing without explicit user authorization.
- Use `docker-compose`, not `docker compose`, on the Ubuntu host.
- Use TDD for Python behavior and run the full existing test and Ruff suites before deployment.

---

### Task 1: Add a Safe ETL Command-Line Entry

**Files:**
- Create: `src/jobflow/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `jobflow.workers.etl.run_boss_snapshot(path: pathlib.Path) -> None`
- Consumes: `jobflow.adapters.boss.SnapshotError`
- Produces: `jobflow.cli.main(argv: list[str] | None = None) -> int`
- Produces: module invocation `python -m jobflow.cli SNAPSHOT_PATH`

- [ ] **Step 1: Write tests for success, source-data failure, unexpected failure, and missing arguments**

```python
from pathlib import Path

import pytest

from jobflow.adapters.boss import SnapshotError
from jobflow import cli


def test_main_runs_snapshot_and_reports_success(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "run_boss_snapshot", lambda path: calls.append(path))

    result = cli.main(["snapshot.json"])

    assert result == 0
    assert calls == [Path("snapshot.json")]
    assert "ETL completed: snapshot.json" in capsys.readouterr().out


def test_main_reports_snapshot_error_without_traceback(monkeypatch, capsys):
    def fail(path):
        raise SnapshotError("missing jobs field")

    monkeypatch.setattr(cli, "run_boss_snapshot", fail)

    result = cli.main(["broken.json"])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.err == "ETL failed: missing jobs field\n"
    assert "Traceback" not in captured.err


def test_main_hides_unexpected_error_details(monkeypatch, capsys):
    def fail(path):
        raise RuntimeError("POSTGRES_PASSWORD=secret")

    monkeypatch.setattr(cli, "run_boss_snapshot", fail)

    result = cli.main(["snapshot.json"])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.err == "ETL failed: RuntimeError\n"
    assert "secret" not in captured.err


def test_main_requires_snapshot_path():
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
```

- [ ] **Step 2: Run the focused tests and verify the import fails**

Run:

```cmd
conda run -n jobflow pytest tests/test_cli.py -q
```

Expected: test collection fails because `jobflow.cli` does not exist.

- [ ] **Step 3: Implement the minimal CLI**

```python
import argparse
from pathlib import Path
import sys

from jobflow.adapters.boss import SnapshotError
from jobflow.workers.etl import run_boss_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process one JobFlow BOSS snapshot")
    parser.add_argument("snapshot", type=Path, help="path to the BOSS snapshot JSON file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run_boss_snapshot(args.snapshot)
    except SnapshotError as exc:
        print(f"ETL failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ETL failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(f"ETL completed: {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the focused tests and CLI help**

Run:

```cmd
conda run -n jobflow pytest tests/test_cli.py -q
conda run -n jobflow python -m jobflow.cli --help
```

Expected: four tests pass, and help shows the required `snapshot` positional argument.

- [ ] **Step 5: Review the task diff without staging or committing**

Run:

```cmd
git diff --check -- src/jobflow/cli.py tests/test_cli.py
git status --short
```

Expected: no whitespace errors; all pre-existing AI/WeCom changes remain present and untouched.

---

### Task 2: Add API Liveness and Database Readiness

**Files:**
- Create: `src/jobflow/api/dependencies.py`
- Create: `src/jobflow/api/health.py`
- Create: `tests/api/test_health.py`
- Modify: `src/jobflow/api/analytics.py`
- Modify: `src/jobflow/api/app.py`

**Interfaces:**
- Produces: `jobflow.api.dependencies.get_connection()` FastAPI yield dependency
- Produces: `GET /health -> {"status": "ok"}` without a database call
- Produces: `GET /ready -> {"status": "ready"}` after `SELECT 1`
- Preserves: `jobflow.api.analytics.get_connection` as an imported module name so existing dependency overrides continue to work

- [ ] **Step 1: Write focused health and readiness tests**

```python
from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.dependencies import get_connection
from jobflow.api.app import create_app


def test_health_does_not_open_database():
    app = create_app()
    connection_dependency = Mock(side_effect=AssertionError("database should not be used"))
    app.dependency_overrides[get_connection] = connection_dependency
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connection_dependency.assert_not_called()


def test_ready_executes_database_probe():
    connection = Mock()
    connection.cursor.return_value.fetchone.return_value = (1,)
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    connection.cursor.return_value.execute.assert_called_once_with("SELECT 1")


def test_ready_hides_database_error_details():
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = RuntimeError("database secret")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text
```

- [ ] **Step 2: Run the focused tests and verify the new dependency module is missing**

Run:

```cmd
conda run -n jobflow pytest tests/api/test_health.py -q
```

Expected: collection fails because `jobflow.api.dependencies` does not exist.

- [ ] **Step 3: Move the shared dependency without changing its behavior**

Create `src/jobflow/api/dependencies.py`:

```python
from jobflow.db.connection import connect_postgres


def get_connection():
    connection = connect_postgres()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
```

In `src/jobflow/api/analytics.py`, remove the local `get_connection()` function and replace the `connect_postgres` import with:

```python
from jobflow.api.dependencies import get_connection
```

- [ ] **Step 4: Add the health router**

Create `src/jobflow/api/health.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection

router = APIRouter()


@router.get("/health")
def get_health():
    return {"status": "ok"}


@router.get("/ready")
def get_readiness(connection=Depends(get_connection)):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        if cursor.fetchone() != (1,):
            raise RuntimeError("unexpected readiness result")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return {"status": "ready"}
```

In `src/jobflow/api/app.py`, preserve the existing analytics and uncommitted reports imports, then add:

```python
from jobflow.api.health import router as health_router
```

Inside `create_app()`, add this before the analytics router:

```python
app.include_router(health_router)
```

- [ ] **Step 5: Run focused and existing API tests**

Run:

```cmd
conda run -n jobflow pytest tests/api/test_health.py tests/api/test_analytics.py -q
```

Expected: all selected tests pass, including the existing analytics dependency overrides.

- [ ] **Step 6: Review the task diff without losing experimental routes**

Run:

```cmd
git diff --check -- src/jobflow/api/dependencies.py src/jobflow/api/health.py src/jobflow/api/analytics.py src/jobflow/api/app.py tests/api/test_health.py
git diff -- src/jobflow/api/app.py
```

Expected: `app.py` still includes the user's uncommitted reports router and now also includes `health_router`; nothing is staged.

---

### Task 3: Build One Non-Root JobFlow Image

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Produces: local image `jobflow-app:local`
- Produces: default process `uvicorn jobflow.api.app:app --host 0.0.0.0 --port 8000`
- Consumes: repository `pyproject.toml`, `README.md`, and `src/`

- [ ] **Step 1: Add the build-context deny list**

Create `.dockerignore`:

```dockerignore
.git
.gitignore
.env
.env.*
!.env.example
.pytest_cache
.pytest_tmp
.ruff_cache
.mypy_cache
__pycache__
*.py[cod]
.venv
venv
build
dist
*.egg-info
data
docs
tests
logs
*.log
```

- [ ] **Step 2: Add the shared production Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system jobflow \
    && adduser --system --ingroup jobflow jobflow

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

USER jobflow

CMD ["uvicorn", "jobflow.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Build the image**

Run from Windows with Docker Desktop available:

```cmd
docker build -t jobflow-app:local .
```

Expected: build exits `0` and the final image is tagged `jobflow-app:local`.

- [ ] **Step 4: Verify the image user, Python version, package import, and excluded secrets**

Run:

```cmd
docker run --rm jobflow-app:local id
docker run --rm --entrypoint python jobflow-app:local --version
docker run --rm --entrypoint python jobflow-app:local -c "import jobflow; print(jobflow.__file__)"
docker run --rm --entrypoint sh jobflow-app:local -c "test ! -e /app/.env && test ! -e /app/data"
```

Expected: user is not root, Python is 3.12.x, `jobflow` imports from `/usr/local/lib/...`, and the last command exits `0` without output.

- [ ] **Step 5: Review the task diff**

Run:

```cmd
git diff --check -- Dockerfile .dockerignore
git status --short
```

Expected: no whitespace errors and no existing user changes are removed.

---

### Task 4: Extend Compose with Migration, ETL, and API Services

**Files:**
- Modify: `compose.yaml`
- Modify: `.env.example`
- Create: `docs/ubuntu-deployment.md`

**Interfaces:**
- Produces: `docker-compose run --rm migrate`
- Produces: `docker-compose run --rm etl /data/raw/inbox/boss_jobs.json`
- Produces: `docker-compose up -d postgres api`
- Consumes: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and host `POSTGRES_PORT`
- Consumes: optional `API_BIND_HOST` and `API_PORT`

- [ ] **Step 1: Extend `.env.example` without removing current experimental variables**

Add these lines after `POSTGRES_PORT`:

```dotenv
API_BIND_HOST=127.0.0.1
API_PORT=8000
```

`127.0.0.1` is the safe local default. The Ubuntu server will set `API_BIND_HOST=0.0.0.0` only after UFW is configured.

- [ ] **Step 2: Replace `compose.yaml` with the four-service definition**

```yaml
x-jobflow-app: &jobflow-app
  build:
    context: .
  image: jobflow-app:local
  env_file:
    - .env
  environment:
    POSTGRES_HOST: postgres
    POSTGRES_PORT: "5432"
  depends_on:
    postgres:
      condition: service_healthy

services:
  postgres:
    image: postgres:18-alpine
    env_file:
      - .env
    ports:
      - "127.0.0.1:${POSTGRES_PORT}:5432"
    volumes:
      - postgres_data_v1:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

  migrate:
    image: postgres:18-alpine
    profiles: ["tools"]
    env_file:
      - .env
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./migrations:/migrations:ro
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        set -eu
        for migration in /migrations/*.sql; do
          echo "Applying $${migration}"
          PGPASSWORD="$${POSTGRES_PASSWORD}" psql \
            -v ON_ERROR_STOP=1 \
            -h "$${POSTGRES_HOST}" \
            -p "$${POSTGRES_PORT}" \
            -U "$${POSTGRES_USER}" \
            -d "$${POSTGRES_DB}" \
            -f "$${migration}"
        done

  etl:
    <<: *jobflow-app
    profiles: ["tools"]
    volumes:
      - ./data/raw:/data/raw:ro
    entrypoint: ["python", "-m", "jobflow.cli"]

  api:
    <<: *jobflow-app
    ports:
      - "${API_BIND_HOST:-127.0.0.1}:${API_PORT:-8000}:8000"
    command: ["uvicorn", "jobflow.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)",
        ]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  postgres_data_v1:
```

- [ ] **Step 3: Validate the Compose model on Windows**

Run:

```cmd
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml --profile tools config --services
```

Expected: the first command exits `0`; the second lists `postgres`, `migrate`, `etl`, and `api`.

- [ ] **Step 4: Write the Ubuntu runbook**

Create `docs/ubuntu-deployment.md` with these exact operational sections and commands:

````markdown
# Ubuntu 局域网部署

## 启动数据库并执行迁移

```bash
docker-compose -f compose.yaml up -d postgres
docker-compose -f compose.yaml run --rm migrate
```

## 手动处理快照

```bash
docker-compose -f compose.yaml run --rm etl \
  /data/raw/inbox/boss_jobs.json
```

## 启动 API

```bash
docker-compose -f compose.yaml up -d api
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

## 查看状态和日志

```bash
docker-compose -f compose.yaml ps
docker-compose -f compose.yaml logs --tail=100 api
```

## 停止服务

```bash
docker-compose -f compose.yaml stop api postgres
```

不要提交 `.env` 或 `data/raw/`。PostgreSQL 端口只绑定 `127.0.0.1`；API 端口由 UFW 限制为局域网访问。
````

- [ ] **Step 5: Build through Compose and check the default service set**

Run:

```cmd
docker compose -f compose.yaml build api etl
docker compose -f compose.yaml config --services
```

Expected: the build exits `0`; without `--profile tools`, only `postgres` and `api` are listed, so ETL cannot start accidentally during ordinary `up`.

- [ ] **Step 6: Review configuration changes without staging secrets or experimental code**

Run:

```cmd
git diff --check -- compose.yaml .env.example docs/ubuntu-deployment.md
git status --short
```

Expected: `.env` and `data/raw` do not appear; the pre-existing AI/WeCom files remain untouched.

---

### Task 5: Run Full Local Quality Gates

**Files:**
- Test only; no planned source edits

**Interfaces:**
- Verifies all new and existing Python behavior, formatting, packaging, and Compose configuration

- [ ] **Step 1: Run the full offline test suite**

Run:

```cmd
conda run -n jobflow pytest -q
```

Expected: all tests pass; the total must be greater than the previous stable count because the CLI and health tests are new.

- [ ] **Step 2: Run Ruff checks**

Run:

```cmd
conda run -n jobflow ruff check .
conda run -n jobflow ruff format --check .
```

Expected: both commands exit `0`.

- [ ] **Step 3: Rebuild the final image without cache**

Run:

```cmd
docker build --no-cache -t jobflow-app:local .
```

Expected: the image builds successfully from the repository files declared in `.dockerignore`.

- [ ] **Step 4: Inspect the complete working tree and stop before Git mutation**

Run:

```cmd
git diff --check
git status --short --branch
```

Expected: no whitespace errors. Report deployment files separately from the pre-existing AI/WeCom experiment. Do not stage, commit, or push until the user explicitly authorizes it.

---

### Task 6: Publish Only the Approved Deployment Change

**Files:**
- Deployment files from Tasks 1-4
- Existing uncommitted AI/WeCom files must remain unstaged

**Interfaces:**
- Produces: one reviewable deployment commit on `main`
- Produces: a pushed commit that Ubuntu can pull using its read-only Deploy Key

- [ ] **Step 1: Obtain explicit user authorization to stage and commit**

Required user instruction: an explicit request such as “提交部署改动”. Without it, stop after Task 5 and report the exact file list.

- [ ] **Step 2: Stage only new files and files without unrelated hunks**

Run only after authorization:

```cmd
git add Dockerfile .dockerignore compose.yaml docs/ubuntu-deployment.md docs/superpowers/specs/2026-08-14-ubuntu-container-deployment-design.md docs/superpowers/plans/2026-08-14-ubuntu-container-deployment.md src/jobflow/cli.py src/jobflow/api/dependencies.py src/jobflow/api/health.py src/jobflow/api/analytics.py tests/test_cli.py tests/api/test_health.py
```

Do not stage `.env.example` or `src/jobflow/api/app.py` wholesale because both contain unrelated AI/WeCom changes.

- [ ] **Step 3: Stage only the deployment hunks from dirty shared files**

Use `apply_patch` to create `deployment-shared-files.patch` with this exact content. It is based on the stable `HEAD`, so the unrelated working-tree AI/WeCom lines are not included:

```diff
diff --git a/.env.example b/.env.example
--- a/.env.example
+++ b/.env.example
@@ -3,3 +3,5 @@ POSTGRES_DB=jobflow
 POSTGRES_USER=jobflow
 POSTGRES_PASSWORD=replace_with_a_local_password
-POSTGRES_PORT=5432
\ No newline at end of file
+POSTGRES_PORT=5432
+API_BIND_HOST=127.0.0.1
+API_PORT=8000
diff --git a/src/jobflow/api/app.py b/src/jobflow/api/app.py
--- a/src/jobflow/api/app.py
+++ b/src/jobflow/api/app.py
@@ -3,1 +3,2 @@
 from jobflow.api.analytics import router as analytics_router
+from jobflow.api.health import router as health_router
@@ -7,2 +8,3 @@ def create_app() -> FastAPI:
     app = FastAPI(title="JobFlow Analytics API")
+    app.include_router(health_router)
     app.include_router(analytics_router)
```

Apply that exact patch to the index with:

```cmd
git apply --cached --check deployment-shared-files.patch
git apply --cached deployment-shared-files.patch
```

Delete only the temporary patch after `git diff --cached` proves the two intended hunks are staged. The working-tree AI/WeCom hunks must remain unstaged.

- [ ] **Step 4: Review staged content for scope and secrets**

Run:

```cmd
git diff --cached --check
git diff --cached --stat
git diff --cached
git status --short
```

Expected: only deployment code, tests, spec, plan, and runbook are staged. No real `.env`, snapshot, OpenAI key, Webhook, Token, Cookie, private key, AI module, channel module, report module, or report test is staged.

- [ ] **Step 5: Commit and push only after the staged review passes**

Run:

```cmd
git commit -m "feat: add Ubuntu container deployment"
git push origin main
```

Expected: commit and push both succeed; working-tree AI/WeCom experiment remains uncommitted.

---

### Task 7: Deploy and Verify on Ubuntu

**Files:**
- Ubuntu checkout: `<JOBFLOW_DIR>`
- Ubuntu private configuration: `<JOBFLOW_DIR>/.env`
- Uploaded snapshot: `<JOBFLOW_DIR>/data/raw/inbox/boss_jobs.json`

**Interfaces:**
- Produces: healthy PostgreSQL and API containers
- Produces: one successful 30-row ETL batch
- Produces: LAN endpoints at `http://<SERVER_IP>:8000`

- [ ] **Step 1: Pull the approved deployment commit and confirm the revision**

Run on Ubuntu:

```bash
cd <JOBFLOW_DIR>
git pull --ff-only
git status --short --branch
git log -1 --oneline
```

Expected: `main` matches `origin/main`; the uploaded ignored snapshot remains available.

- [ ] **Step 2: Add API bind settings without displaying secrets**

Run on Ubuntu:

```bash
grep -q '^API_BIND_HOST=' .env || printf '\nAPI_BIND_HOST=0.0.0.0\n' >> .env
grep -q '^API_PORT=' .env || printf 'API_PORT=8000\n' >> .env
chmod 600 .env
```

Expected: commands exit `0`. Do not run `cat .env`.

- [ ] **Step 3: Protect SSH first, then allow only the LAN API port**

Run on Ubuntu:

```bash
sudo ufw allow OpenSSH
sudo ufw allow from <LAN_CIDR> to any port 8000 proto tcp
sudo ufw --force enable
sudo ufw status numbered
```

Expected: OpenSSH remains allowed and port 8000 is allowed only from `<LAN_CIDR>`; no rule exposes port 5432.

- [ ] **Step 4: Validate Compose 1.29.2 and build the application image**

Run on Ubuntu:

```bash
docker-compose -f compose.yaml config --quiet
docker-compose -f compose.yaml build api etl
```

Expected: both commands exit `0` and produce `jobflow-app:local`.

- [ ] **Step 5: Start PostgreSQL and run idempotent migrations**

Run on Ubuntu:

```bash
docker-compose -f compose.yaml up -d postgres
docker-compose -f compose.yaml run --rm migrate
```

Expected: all five migration filenames are printed in order and the command exits `0`.

- [ ] **Step 6: Run the uploaded snapshot through ETL**

Run on Ubuntu:

```bash
docker-compose -f compose.yaml run --rm etl \
  /data/raw/inbox/boss_jobs.json
```

Expected: command exits `0` and prints `ETL completed: /data/raw/inbox/boss_jobs.json`.

- [ ] **Step 7: Verify the latest batch and database counts without revealing credentials**

Run on Ubuntu:

```bash
docker-compose -f compose.yaml exec -T postgres \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT id, status, row_count FROM ops.batches ORDER BY id DESC LIMIT 1;" \
  -c "SELECT COUNT(*) AS raw_rows FROM raw.job_records WHERE batch_id = (SELECT MAX(id) FROM ops.batches);" \
  -c "SELECT COUNT(*) AS core_jobs FROM core.jobs;" \
  -c "SELECT COUNT(*) AS city_rows FROM mart.city_job_counts;" \
  -c "SELECT COUNT(*) AS salary_rows FROM mart.city_salary_stats;" \
  -c "SELECT COUNT(*) AS skill_rows FROM mart.skill_job_counts;"'
```

Expected: latest batch is `succeeded` with `row_count = 30`; latest raw batch has `30`; core has `30`; each mart count is greater than zero.

- [ ] **Step 8: Start and probe the API on Ubuntu**

Run on Ubuntu:

```bash
docker-compose -f compose.yaml up -d api
docker-compose -f compose.yaml ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail 'http://127.0.0.1:8000/analytics/cities?limit=3'
curl --fail 'http://127.0.0.1:8000/analytics/salaries/cities?limit=3'
curl --fail 'http://127.0.0.1:8000/analytics/skills?limit=3'
```

Expected: containers are healthy; health and readiness return `200`; all analysis endpoints return JSON arrays.

- [ ] **Step 9: Probe the API from Windows over the LAN**

Run in Windows CMD:

```cmd
curl --fail http://<SERVER_IP>:8000/health
curl --fail http://<SERVER_IP>:8000/ready
curl --fail "http://<SERVER_IP>:8000/analytics/cities?limit=3"
curl --fail "http://<SERVER_IP>:8000/analytics/salaries/cities?limit=3"
curl --fail "http://<SERVER_IP>:8000/analytics/skills?limit=3"
```

Expected: the first two commands return status objects and the three analytics commands return non-empty JSON arrays.

- [ ] **Step 10: Record final operational evidence**

Capture these non-secret facts for the daily summary and Obsidian update after all checks pass:

```text
deployed commit hash
Docker image tag
container health states
latest ETL batch id/status/row_count
raw/core counts
mart row counts
five successful LAN endpoint checks
```

Do not record `.env` contents, password hashes, deploy private keys, OpenAI credentials, or Webhook values.
