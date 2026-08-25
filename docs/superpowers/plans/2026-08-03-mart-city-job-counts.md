# Mart City Job Counts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a read-only PostgreSQL View that reports the current number of jobs grouped by city.

**Architecture:** core.jobs remains the only fact source. A normal View in the mart schema computes COUNT(*) GROUP BY city at query time, so the ETL Worker needs no refresh hook.

**Tech Stack:** Python 3.12, PostgreSQL 18, psycopg 3, pytest, Ruff, Docker Compose, Windows CMD.

## Global Constraints

- The learner writes business code manually; advance one independently verifiable microtask at a time.
- Use TDD for the migration contract; use real PostgreSQL for View behavior.
- The metric counts all current rows in core.jobs, not a time window.
- The output columns are city TEXT and job_count BIGINT.
- Do not add salary, skill, API, materialized View, or aggregate-table behavior.
- Do not read or display .env, passwords, tokens, or connection secrets.
- Do not run git push automatically.

---

### Task 1: Create the mart city-count View migration

**Files:**
- Create: tests/db/test_mart_migration.py
- Create: migrations/004_create_mart_city_job_counts.sql

**Interfaces:**
- Consumes: core.jobs(city)
- Produces: mart.city_job_counts(city, job_count)

- [ ] Step 1: Write the failing migration contract test

~~~python
from pathlib import Path


def test_mart_city_job_counts_migration_defines_view():
    migration_path = Path("migrations/004_create_mart_city_job_counts.sql")

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE SCHEMA IF NOT EXISTS mart" in sql
    assert "CREATE OR REPLACE VIEW mart.city_job_counts" in sql
    assert "city" in sql
    assert "COUNT(*) AS job_count" in sql
    assert "FROM core.jobs" in sql
    assert "GROUP BY city" in sql
~~~

- [ ] Step 2: Run the test and verify red

~~~cmd
pytest tests/db/test_mart_migration.py -q
~~~

Expected: 1 failed because migration 004 does not exist.

- [ ] Step 3: Write the minimal migration

~~~sql
CREATE SCHEMA IF NOT EXISTS mart;

CREATE OR REPLACE VIEW mart.city_job_counts AS
SELECT
    city,
    COUNT(*) AS job_count
FROM core.jobs
GROUP BY city;
~~~

- [ ] Step 4: Run the task checks

~~~cmd
pytest tests/db/test_mart_migration.py -q
ruff check tests/db/test_mart_migration.py
ruff format --check tests/db/test_mart_migration.py
git diff --check
~~~

Expected: 1 passed, Ruff passes, and git diff --check prints nothing.

- [ ] Step 5: Review and commit

~~~cmd
git add migrations/004_create_mart_city_job_counts.sql tests/db/test_mart_migration.py
git diff --cached
git commit -m "feat: 添加城市岗位数量分析视图"
~~~

---

### Task 2: Verify the View dynamically in real PostgreSQL

**Files:**
- Modify: tests/integration/test_postgres_connection.py

**Interfaces:**
- Consumes: applied migration 004 and existing insert_job()
- Produces: a dynamic mart.city_job_counts query result without a refresh call

- [ ] Step 1: Apply migration 004 to local PostgreSQL

~~~cmd
docker compose up -d postgres
docker compose exec -T postgres psql -U jobflow -d jobflow < migrations/004_create_mart_city_job_counts.sql
~~~

Expected: PostgreSQL reports CREATE SCHEMA and CREATE VIEW, or harmless notices if already applied.

- [ ] Step 2: Add the real View test

~~~python
from uuid import uuid4


def test_city_job_counts_view_updates_without_refresh(postgres_connection):
    source = "mart_integration"
    city = f"mart-city-{uuid4()}"

    first_job = JobRecord(
        source=source,
        external_id=f"{city}-001",
        title="Python开发工程师",
        company="分析测试公司",
        city=city,
        detail_url="https://example.com/mart-001",
    )
    second_job = JobRecord(
        source=source,
        external_id=f"{city}-002",
        title="数据工程师",
        company="分析测试公司",
        city=city,
        detail_url="https://example.com/mart-002",
    )

    insert_job(postgres_connection, first_job)
    insert_job(postgres_connection, second_job)

    cursor = postgres_connection.cursor()
    cursor.execute(
        "SELECT city, job_count FROM mart.city_job_counts WHERE city = %s",
        (city,),
    )
    assert cursor.fetchone() == (city, 2)

    third_job = JobRecord(
        source=source,
        external_id=f"{city}-003",
        title="数据分析师",
        company="分析测试公司",
        city=city,
        detail_url="https://example.com/mart-003",
    )
    insert_job(postgres_connection, third_job)

    cursor.execute(
        "SELECT city, job_count FROM mart.city_job_counts WHERE city = %s",
        (city,),
    )
    assert cursor.fetchone() == (city, 3)
~~~

- [ ] Step 3: Run the focused real-database test

Run in the CMD where the jobflow environment and PostgreSQL variables are loaded:

~~~cmd
pytest tests/integration/test_postgres_connection.py::test_city_job_counts_view_updates_without_refresh -q
~~~

Expected: 1 passed.

- [ ] Step 4: Run all quality gates

~~~cmd
pytest -q
ruff check .
ruff format --check .
git diff --check
~~~

Expected: 55 passed, Ruff passes, formatting passes, and git diff --check prints nothing.

- [ ] Step 5: Review and commit

~~~cmd
git add tests/integration/test_postgres_connection.py
git diff --cached
git commit -m "test: 验证城市岗位数量视图动态更新"
git status --short --branch
~~~
