# City Analytics API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a fixed, read-only `GET /analytics/cities` endpoint that returns the current city job counts from `mart.city_job_counts`.

**Architecture:** Keep database access in `src/jobflow/db/analytics.py`, HTTP behavior in `src/jobflow/api/analytics.py`, and application construction in `src/jobflow/api/app.py`. The endpoint calls one parameterized `SELECT` against the existing ordinary PostgreSQL View and never accepts arbitrary SQL, table names, or write operations.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, psycopg 3, pytest, FastAPI TestClient/httpx, PostgreSQL 18, Ruff, Docker Compose, Windows CMD.

## Global Constraints

- Advance one independently verifiable microtask at a time; the learner writes business code manually.
- Use TDD: red contract test, minimal implementation, green test, quality checks, then a separate Git commit.
- `GET /analytics/cities` is the only endpoint in this scope.
- `limit` defaults to `20` and accepts only integers from `1` through `100`.
- The query reads only `mart.city_job_counts` and orders by `job_count DESC, city ASC`.
- Empty data returns HTTP `200` with `[]`; database failures return HTTP `503` without internal details.
- Do not modify the ETL Worker write transaction boundary or expose `raw` data, individual jobs, credentials, SQL, or stack traces.
- Do not read or display `.env`, passwords, tokens, or connection secrets.
- Do not run `git push` automatically; the learner runs commit commands after review.

---

### Task 1: Add the city-count database query function

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/db/test_analytics.py`
- Create: `src/jobflow/db/analytics.py`

**Interfaces:**
- Consumes: an existing psycopg connection-like object and `limit: int`.
- Produces: `list[dict[str, object]]` containing `city` and `job_count` keys.
- Exact function: `list_city_job_counts(connection, limit: int) -> list[dict[str, object]]`.

- [ ] **Step 1: Add the dependencies needed by the API tests and local server**

Add these entries to the existing project dependencies:

```toml
"fastapi>=0.115,<1",
"uvicorn[standard]>=0.34,<1",
```

Add these entries to the existing `dev` optional dependencies:

```toml
"httpx>=0.28,<1",
```

Install the project in the active CMD environment:

```cmd
python -m pip install -e ".[dev]"
```

Expected: installation completes without exposing or printing `.env` contents.

- [ ] **Step 2: Write the failing database-query test**

Create `tests/db/test_analytics.py`:

```python
from jobflow.db.analytics import list_city_job_counts


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return [("Lanzhou", 12), ("Hangzhou", 8)]


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self):
        return self.fake_cursor


def test_list_city_job_counts_queries_the_mart_view_with_limit():
    connection = FakeConnection()

    result = list_city_job_counts(connection, limit=20)

    sql, params = connection.fake_cursor.executed[0]
    assert "FROM mart.city_job_counts" in sql
    assert "ORDER BY job_count DESC, city ASC" in sql
    assert "LIMIT %s" in sql
    assert params == (20,)
    assert result == [
        {"city": "Lanzhou", "job_count": 12},
        {"city": "Hangzhou", "job_count": 8},
    ]
```

Run:

```cmd
pytest tests\db\test_analytics.py::test_list_city_job_counts_queries_the_mart_view_with_limit -q
```

Expected: FAIL because `jobflow.db.analytics` and `list_city_job_counts` do not exist yet.

- [ ] **Step 3: Write the minimal query implementation**

Create `src/jobflow/db/analytics.py`:

```python
def list_city_job_counts(connection, limit: int) -> list[dict[str, object]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT city, job_count
        FROM mart.city_job_counts
        ORDER BY job_count DESC, city ASC
        LIMIT %s
        """,
        (limit,),
    )

    return [
        {"city": city, "job_count": job_count}
        for city, job_count in cursor.fetchall()
    ]
```

- [ ] **Step 4: Run the focused query test**

```cmd
pytest tests\db\test_analytics.py::test_list_city_job_counts_queries_the_mart_view_with_limit -q
```

Expected: `1 passed`.

- [ ] **Step 5: Run query-layer quality checks and commit**

```cmd
ruff check src\jobflow\db\analytics.py tests\db\test_analytics.py
ruff format --check src\jobflow\db\analytics.py tests\db\test_analytics.py
git diff --check
git add pyproject.toml src\jobflow\db\analytics.py tests\db\test_analytics.py
git diff --cached --check
git commit -m "feat: 添加城市岗位数量查询函数"
```

Expected: Ruff passes, the commit succeeds, and no `.env` or secret file is staged.

---

### Task 2: Add the FastAPI application and fixed route

**Files:**
- Create: `src/jobflow/api/__init__.py`
- Create: `src/jobflow/api/app.py`
- Create: `src/jobflow/api/analytics.py`
- Create: `tests/api/test_analytics.py`

**Interfaces:**
- Consumes: `list_city_job_counts(connection, limit)` from Task 1 and `connect_postgres()`.
- Produces: `create_app() -> FastAPI`, module-level `app`, and `GET /analytics/cities`.

- [ ] **Step 1: Write the failing API tests**

Create `tests/api/test_analytics.py`:

```python
from unittest.mock import Mock

from fastapi.testclient import TestClient

from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app


def client_with_rows(rows):
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = rows
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    return TestClient(app), app, connection


def test_city_analytics_returns_rows_and_default_limit():
    client, app, connection = client_with_rows([("Lanzhou", 12)])
    try:
        response = client.get("/analytics/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"city": "Lanzhou", "job_count": 12}]
    _, params = connection.cursor.return_value.execute.call_args.args
    assert params == (20,)


def test_city_analytics_rejects_limit_outside_range():
    app = create_app()
    client = TestClient(app)

    assert client.get("/analytics/cities?limit=0").status_code == 422
    assert client.get("/analytics/cities?limit=101").status_code == 422


def test_city_analytics_returns_empty_array_when_view_has_no_rows():
    client, app, _ = client_with_rows([])
    try:
        response = client.get("/analytics/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_city_analytics_hides_database_error_details():
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = RuntimeError(
        "internal database detail"
    )
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    client = TestClient(app)
    try:
        response = client.get("/analytics/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "analytics database unavailable"}
```

Run:

```cmd
pytest tests\api\test_analytics.py -q
```

Expected: FAIL because the API package and route do not exist yet.

- [ ] **Step 2: Implement the connection dependency, route, and app factory**

Create `src/jobflow/api/__init__.py` as an empty package marker.

Create `src/jobflow/api/analytics.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query

from jobflow.db.analytics import list_city_job_counts
from jobflow.db.connection import connect_postgres

router = APIRouter(prefix="/analytics")


def get_connection():
    connection = connect_postgres()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


@router.get("/cities")
def get_city_job_counts(
    limit: int = Query(default=20, ge=1, le=100),
    connection=Depends(get_connection),
):
    try:
        return list_city_job_counts(connection, limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="analytics database unavailable",
        ) from exc
```

Create `src/jobflow/api/app.py`:

```python
from fastapi import FastAPI

from jobflow.api.analytics import router as analytics_router


def create_app() -> FastAPI:
    app = FastAPI(title="JobFlow Analytics API")
    app.include_router(analytics_router)
    return app


app = create_app()
```

The route uses `Query(default=20, ge=1, le=100)`, calls `list_city_job_counts`, returns its list directly, and converts database exceptions to `HTTPException(status_code=503, detail="analytics database unavailable")` without exposing the original message.

`src/jobflow/api/app.py` must provide `create_app()`, register the analytics router, and expose `app = create_app()`.

`src/jobflow/api/__init__.py` can remain an empty package marker.

- [ ] **Step 3: Run the API tests**

```cmd
pytest tests\api\test_analytics.py -q
```

Expected: all API tests pass, including the default limit and `422` boundary cases.

- [ ] **Step 4: Run API quality checks and commit**

```cmd
ruff check src\jobflow\api tests\api
ruff format --check src\jobflow\api tests\api
git diff --check
git add src\jobflow\api tests\api
git diff --cached --check
git commit -m "feat: 添加城市岗位统计只读接口"
```

Expected: all checks pass and only API files are included in this commit.

---

### Task 3: Verify the API against real PostgreSQL

**Files:**
- Modify: `tests/integration/test_postgres_connection.py`

**Interfaces:**
- Consumes: `create_app()`, `get_connection()`, `insert_job()`, and the applied `mart.city_job_counts` View.
- Produces: evidence that HTTP reads the real PostgreSQL aggregate.

- [ ] **Step 1: Write the failing real-database API test**

Add these imports to `tests/integration/test_postgres_connection.py`:

```python
from fastapi.testclient import TestClient

from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app
```

Then add this test:

```python
def test_city_analytics_api_reads_real_postgres(postgres_connection):
    city = f"api-mart-test-{uuid4()}"
    source = "integration_api_mart"

    for index in (1, 2):
        insert_job(
            postgres_connection,
            JobRecord(
                source=source,
                external_id=f"{city}-{index}",
                title=f"API Test Job {index}",
                company="API Test Company",
                city=city,
                detail_url=f"https://example.com/{city}-{index}",
            ),
        )

    app = create_app()
    app.dependency_overrides[get_connection] = lambda: postgres_connection
    client = TestClient(app)
    try:
        response = client.get("/analytics/cities?limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"city": city, "job_count": 2}]
```

Run:

```cmd
docker compose up -d postgres
pytest tests\integration\test_postgres_connection.py::test_city_analytics_api_reads_real_postgres -q
```

Expected: FAIL until the integration test and imports are added.

- [ ] **Step 2: Implement only the integration test**

Use `uuid4()` for the city and external IDs. Clear `app.dependency_overrides` in a `finally` block. Do not commit the inserted rows; the existing fixture rollback must clean up the test transaction.

- [ ] **Step 3: Run the focused integration test**

```cmd
pytest tests\integration\test_postgres_connection.py::test_city_analytics_api_reads_real_postgres -q
```

Expected: `1 passed` while PostgreSQL is healthy.

- [ ] **Step 4: Run the complete project gates**

```cmd
pytest -q
ruff check .
ruff format --check .
git diff --check
```

Expected: `61 passed` after the one query test, four API tests, and one integration test are present, Ruff and formatting pass, and `git diff --check` prints no whitespace errors.

- [ ] **Step 5: Review and commit**

```cmd
git status --short --branch
git diff --stat
git add tests/integration/test_postgres_connection.py
git diff --cached --check
git commit -m "test: 验证城市岗位统计接口读取真实数据库"
git status --short --branch
```

Expected: the working tree is clean. Do not run `git push` automatically.

---

## Handoff

After Task 3, the next separate design decision is whether to add more mart indicators (salary or skills) or to expose additional fixed read-only endpoints. Do not build a generic semantic query protocol until that scope is explicitly approved.
