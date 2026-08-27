# Raw Job Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a traceable `raw.job_records` layer and make the ETL Worker save each original BOSS job together with its normalized `core.jobs` record.

**Architecture:** Each source observation is stored once per ETL batch as JSONB and linked to `ops.batches`. `run_job_batch(raw_jobs, jobs)` owns the shared transaction: the running batch is committed first, raw and core writes then succeed together or roll back together, and the final batch state is committed separately.

**Tech Stack:** Python 3.12, PostgreSQL 18, psycopg 3, pytest, Ruff, Docker Compose, Windows CMD.

## Global Constraints

- The learner writes all business code manually; execute one independently verifiable microtask at a time.
- Use TDD: failing test, minimal implementation, passing test, then quality checks.
- Use Windows CMD commands in mentoring instructions.
- Do not read or display `.env`, passwords, tokens, or other secrets.
- Do not run `git push` automatically.
- One raw source job is one `raw.job_records` row.
- Preserve the complete source dictionary in a non-null `payload JSONB` column.
- Allow the same source job across different batches, but reject duplicates inside one batch.
- Save raw and core rows in the same Worker transaction.
- Do not implement replay, source-specific raw indexes, FastAPI, mart, or AI features in this plan.

---

## File map

- Create `migrations/003_create_raw_job_records.sql`: define the raw schema, table, foreign key, and batch-scoped uniqueness.
- Create `tests/db/test_raw_migration.py`: offline contract test for the migration text.
- Create `src/jobflow/db/raw_jobs.py`: parameterized single-row and batch raw inserts.
- Create `tests/db/test_raw_jobs.py`: unit tests for SQL parameters, JSONB preservation, batch iteration, and length mismatch.
- Modify `src/jobflow/workers/jobs.py`: place raw and core writes in one transaction.
- Modify `src/jobflow/workers/etl.py`: pass both `raw_jobs` and normalized `jobs` to the Worker.
- Modify `tests/workers/test_worker_jobs.py`: verify raw/core event order and rollback.
- Modify `tests/workers/test_etl.py`: verify both data representations cross the orchestration boundary.
- Modify `tests/integration/test_postgres_connection.py`: verify real PostgreSQL constraints and the complete Worker lifecycle.

---

### Task 1: Create the raw table migration

**Files:**
- Create: `tests/db/test_raw_migration.py`
- Create: `migrations/003_create_raw_job_records.sql`

**Interfaces:**
- Consumes: existing table `ops.batches(id)`
- Produces: `raw.job_records(id, batch_id, source, external_id, payload, ingested_at)`

- [ ] **Step 1: Write the failing migration contract test**

```python
from pathlib import Path


def test_raw_job_records_migration_defines_table_and_constraints():
    migration_path = Path("migrations/003_create_raw_job_records.sql")

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE SCHEMA IF NOT EXISTS raw" in sql
    assert "CREATE TABLE IF NOT EXISTS raw.job_records" in sql
    assert "batch_id BIGINT NOT NULL" in sql
    assert "REFERENCES ops.batches (id)" in sql
    assert "payload JSONB NOT NULL" in sql
    assert "ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP" in sql
    assert "UNIQUE (batch_id, source, external_id)" in sql
```

- [ ] **Step 2: Run the test and verify red**

Run:

```cmd
pytest tests\db\test_raw_migration.py -q
```

Expected: FAIL because `migrations/003_create_raw_job_records.sql` does not exist.

- [ ] **Step 3: Write the minimal migration**

```sql
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.job_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT job_records_batch_id_fkey
        FOREIGN KEY (batch_id)
        REFERENCES ops.batches (id),
    CONSTRAINT job_records_batch_source_external_id_key
        UNIQUE (batch_id, source, external_id)
);
```

- [ ] **Step 4: Run the task tests and quality checks**

Run:

```cmd
pytest tests\db\test_raw_migration.py -q
ruff check tests\db\test_raw_migration.py
ruff format --check tests\db\test_raw_migration.py
git diff --check
```

Expected: `1 passed`, Ruff passes, and `git diff --check` prints nothing.

- [ ] **Step 5: Review and commit**

```cmd
git diff -- migrations\003_create_raw_job_records.sql tests\db\test_raw_migration.py
git add migrations\003_create_raw_job_records.sql tests\db\test_raw_migration.py
git diff --cached
git commit -m "feat: 添加 raw 原始岗位表迁移"
```

---

### Task 2: Add parameterized raw insert functions

**Files:**
- Create: `tests/db/test_raw_jobs.py`
- Create: `src/jobflow/db/raw_jobs.py`

**Interfaces:**
- Consumes: a DB-API connection, `batch_id: int`, source dictionaries, and aligned `JobRecord` objects
- Produces: `insert_raw_job(...)->None` and `insert_raw_jobs(...)->None`

- [ ] **Step 1: Write the failing unit tests**

```python
import pytest
from psycopg.types.json import Jsonb

from jobflow.models.job import JobRecord


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self):
        return self.fake_cursor


def make_job(external_id: str) -> JobRecord:
    return JobRecord(
        source="boss_zhipin",
        external_id=external_id,
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url=f"https://example.com/jobs/{external_id}",
    )


def test_insert_raw_job_preserves_complete_payload_as_jsonb():
    from jobflow.db.raw_jobs import insert_raw_job

    connection = FakeConnection()
    payload = {
        "job_id": "job-001",
        "title": "Python开发工程师",
        "extra_source_field": "必须保留",
    }

    insert_raw_job(
        connection,
        batch_id=101,
        source="boss_zhipin",
        external_id="job-001",
        payload=payload,
    )

    sql, params = connection.fake_cursor.executed[0]

    assert "INSERT INTO raw.job_records" in sql
    assert "(batch_id, source, external_id, payload)" in sql
    assert params[:3] == (101, "boss_zhipin", "job-001")
    assert isinstance(params[3], Jsonb)
    assert params[3].obj == payload


def test_insert_raw_jobs_pairs_raw_payloads_with_normalized_identity():
    from jobflow.db.raw_jobs import insert_raw_jobs

    connection = FakeConnection()
    raw_jobs = [
        {"job_id": "job-001", "title": "Python开发工程师"},
        {"job_id": "job-002", "title": "Java开发工程师"},
    ]
    jobs = [make_job("job-001"), make_job("job-002")]

    insert_raw_jobs(connection, batch_id=101, raw_jobs=raw_jobs, jobs=jobs)

    assert len(connection.fake_cursor.executed) == 2
    first_params = connection.fake_cursor.executed[0][1]
    second_params = connection.fake_cursor.executed[1][1]
    assert first_params[:3] == (101, "boss_zhipin", "job-001")
    assert first_params[3].obj == raw_jobs[0]
    assert second_params[:3] == (101, "boss_zhipin", "job-002")
    assert second_params[3].obj == raw_jobs[1]


def test_insert_raw_jobs_rejects_mismatched_list_lengths():
    from jobflow.db.raw_jobs import insert_raw_jobs

    connection = FakeConnection()

    with pytest.raises(ValueError, match="raw_jobs and jobs must have the same length"):
        insert_raw_jobs(
            connection,
            batch_id=101,
            raw_jobs=[{"job_id": "job-001"}, {"job_id": "job-002"}],
            jobs=[make_job("job-001")],
        )
```

- [ ] **Step 2: Run the tests and verify red**

```cmd
pytest tests\db\test_raw_jobs.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'jobflow.db.raw_jobs'`.

- [ ] **Step 3: Write the minimal database functions**

```python
from psycopg.types.json import Jsonb

from jobflow.models.job import JobRecord


def insert_raw_job(
    connection,
    batch_id: int,
    source: str,
    external_id: str,
    payload: dict[str, str],
) -> None:
    cursor = connection.cursor()
    sql = """
        INSERT INTO raw.job_records (batch_id, source, external_id, payload)
        VALUES (%s, %s, %s, %s)
    """
    params = (batch_id, source, external_id, Jsonb(payload))

    cursor.execute(sql, params)


def insert_raw_jobs(
    connection,
    batch_id: int,
    raw_jobs: list[dict[str, str]],
    jobs: list[JobRecord],
) -> None:
    if len(raw_jobs) != len(jobs):
        raise ValueError("raw_jobs and jobs must have the same length")

    for raw_job, job in zip(raw_jobs, jobs):
        insert_raw_job(
            connection,
            batch_id=batch_id,
            source=job.source,
            external_id=job.external_id,
            payload=raw_job,
        )
```

- [ ] **Step 4: Run tests and quality checks**

```cmd
pytest tests\db\test_raw_jobs.py -q
ruff check src\jobflow\db\raw_jobs.py tests\db\test_raw_jobs.py
ruff format --check src\jobflow\db\raw_jobs.py tests\db\test_raw_jobs.py
git diff --check
```

Expected: `3 passed`, Ruff passes, and the diff check is empty.

- [ ] **Step 5: Review and commit**

```cmd
git diff -- src\jobflow\db\raw_jobs.py tests\db\test_raw_jobs.py
git add src\jobflow\db\raw_jobs.py tests\db\test_raw_jobs.py
git diff --cached
git commit -m "feat: 添加原始岗位批量写入"
```

---

### Task 3: Pass raw jobs through ETL and the Worker transaction

**Files:**
- Modify: `tests/workers/test_etl.py`
- Modify: `tests/workers/test_worker_jobs.py`
- Modify: `src/jobflow/workers/etl.py`
- Modify: `src/jobflow/workers/jobs.py`

**Interfaces:**
- Consumes: `run_job_batch(raw_jobs: list[dict[str, str]], jobs: list[JobRecord])`
- Produces: the event order `start → commit → raw → core → finish → commit → close`

- [ ] **Step 1: Change ETL tests to require both representations**

In `test_run_boss_snapshot_orchestrates_etl`, use this fake and assertions:

```python
def fake_run_job_batch(received_raw_jobs, received_jobs):
    calls["batch_raw_input"] = received_raw_jobs
    calls["batch_job_input"] = received_jobs


assert calls["batch_raw_input"] == raw_jobs
assert calls["batch_job_input"] == jobs
```

Change the database-error fake to:

```python
def failing_run_job_batch(raw_jobs, jobs):
    raise RuntimeError("数据库写入失败")
```

Change the empty-snapshot guard fake to:

```python
def unexpected_batch(raw_jobs, jobs):
    pytest.fail("空岗位不应该进入数据库写入层")
```

- [ ] **Step 2: Change Worker event tests to require raw before core**

Use this raw input in both non-empty event tests:

```python
raw_jobs = [
    {
        "job_id": "job-001",
        "title": "Python开发工程师",
        "boss_name": "示例公司",
        "location": "兰州",
        "job_link": "https://example.com/jobs/001",
    }
]
```

Add this successful raw fake:

```python
def fake_insert_raw_jobs(connection, batch_id, received_raw_jobs, jobs):
    assert connection is fake_connection
    assert batch_id == 101
    assert received_raw_jobs == raw_jobs
    assert jobs == [job]
    events.append("insert_raw_jobs")
```

Patch it with:

```python
monkeypatch.setattr(worker_jobs, "insert_raw_jobs", fake_insert_raw_jobs, raising=False)
```

Call the Worker with:

```python
worker_jobs.run_job_batch(raw_jobs, [job])
```

The successful expected events become:

```python
assert events == [
    ("start_batch", "boss_zhipin"),
    "commit",
    "insert_raw_jobs",
    "insert_jobs",
    ("finish_batch", 101, 1),
    "commit",
    "close",
]
```

Use the same raw fake and call signature in the failure event test. Its expected events become:

```python
assert events == [
    ("start_batch", "boss_zhipin"),
    "commit",
    "insert_raw_jobs",
    "insert_jobs",
    "rollback",
    ("fail_batch", 101, "insert failed"),
    "commit",
    "close",
]
```

In `test_run_job_batch_commits_and_closes_on_success`, add:

```python
raw_jobs = [
    {"job_id": "job-001"},
    {"job_id": "job-002"},
]

monkeypatch.setattr(
    worker_jobs,
    "insert_raw_jobs",
    lambda connection, batch_id, raw_jobs, jobs: None,
    raising=False,
)
```

Replace its Worker call with:

```python
worker_jobs.run_job_batch(raw_jobs, jobs_to_insert)
```

In `test_run_job_batch_rolls_back_and_closes_on_failure`, replace the old call with:

```python
worker_jobs.run_job_batch([], [])
```

- [ ] **Step 3: Run Worker and ETL tests and verify red**

```cmd
pytest tests\workers\test_etl.py tests\workers\test_worker_jobs.py -q
```

Expected: FAIL because the current Worker accepts one argument and does not call `insert_raw_jobs`.

- [ ] **Step 4: Implement the minimal ETL interface**

Replace the final call in `run_boss_snapshot` with:

```python
run_job_batch(raw_jobs, jobs)
```

- [ ] **Step 5: Implement the minimal Worker transaction change**

Add the import:

```python
from jobflow.db.raw_jobs import insert_raw_jobs
```

Change the signature:

```python
def run_job_batch(
    raw_jobs: list[dict[str, str]],
    jobs: list[JobRecord],
) -> None:
```

After the first `commit()` and before `insert_jobs()`, add:

```python
if batch_id is not None:
    insert_raw_jobs(
        connection,
        batch_id=batch_id,
        raw_jobs=raw_jobs,
        jobs=jobs,
    )
```

- [ ] **Step 6: Run tests and quality checks**

```cmd
pytest tests\workers\test_etl.py tests\workers\test_worker_jobs.py -q
pytest -q
ruff check .
ruff format --check .
git diff --check
```

Expected: Worker/ETL tests pass, the full suite reports `48 passed`, Ruff passes, and the diff check is empty.

- [ ] **Step 7: Review and commit**

```cmd
git diff -- src\jobflow\workers\etl.py src\jobflow\workers\jobs.py tests\workers\test_etl.py tests\workers\test_worker_jobs.py
git add src\jobflow\workers\etl.py src\jobflow\workers\jobs.py tests\workers\test_etl.py tests\workers\test_worker_jobs.py
git diff --cached
git commit -m "feat: 将原始岗位接入 ETL Worker"
```

---

### Task 4: Validate raw constraints and Worker behavior in real PostgreSQL

**Files:**
- Modify: `tests/integration/test_postgres_connection.py`

**Interfaces:**
- Consumes: applied migrations 001, 002, and 003 plus `insert_raw_job` and `run_job_batch`
- Produces: real-database evidence for foreign keys, uniqueness, history, success, and rollback

- [ ] **Step 1: Apply migration 003 to local PostgreSQL**

Ensure the container is healthy:

```cmd
docker compose up -d postgres
docker compose ps
```

Apply the migration without printing secrets:

```cmd
docker compose exec -T postgres psql -U jobflow -d jobflow < migrations\003_create_raw_job_records.sql
```

Expected: `CREATE SCHEMA` and `CREATE TABLE`, or harmless notices if already applied.

- [ ] **Step 2: Add imports and a query helper**

```python
from uuid import uuid4

import psycopg

from jobflow.db.raw_jobs import insert_raw_job
from jobflow.workers.jobs import run_job_batch
```

- [ ] **Step 3: Test the foreign key**

```python
def test_raw_job_rejects_missing_batch_in_real_postgres(postgres_connection):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert_raw_job(
            postgres_connection,
            batch_id=9_999_999_999,
            source="integration_test",
            external_id="missing-batch-job",
            payload={"job_id": "missing-batch-job"},
        )
```

- [ ] **Step 4: Test same-batch uniqueness**

```python
def test_raw_job_rejects_duplicate_inside_batch(postgres_connection):
    batch_id = start_batch(postgres_connection, "integration_test")
    payload = {"job_id": "duplicate-job"}

    insert_raw_job(
        postgres_connection,
        batch_id=batch_id,
        source="integration_test",
        external_id="duplicate-job",
        payload=payload,
    )

    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_raw_job(
            postgres_connection,
            batch_id=batch_id,
            source="integration_test",
            external_id="duplicate-job",
            payload=payload,
        )
```

- [ ] **Step 5: Test cross-batch history**

```python
def test_raw_job_keeps_same_job_across_batches(postgres_connection):
    external_id = f"history-{uuid4()}"
    first_batch_id = start_batch(postgres_connection, "integration_test")
    second_batch_id = start_batch(postgres_connection, "integration_test")

    for batch_id in (first_batch_id, second_batch_id):
        insert_raw_job(
            postgres_connection,
            batch_id=batch_id,
            source="integration_test",
            external_id=external_id,
            payload={"job_id": external_id},
        )

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM raw.job_records
        WHERE source = %s AND external_id = %s
        """,
        ("integration_test", external_id),
    )

    assert cursor.fetchone()[0] == 2
```

- [ ] **Step 6: Test the complete successful Worker path**

```python
def test_worker_writes_raw_core_and_success_batch_in_real_postgres():
    external_id = f"worker-success-{uuid4()}"
    source = "integration_worker_success"
    raw_job = {
        "job_id": external_id,
        "title": "Python开发工程师",
        "boss_name": "集成测试公司",
        "location": "兰州",
        "job_link": f"https://example.com/{external_id}",
    }
    job = JobRecord(
        source=source,
        external_id=external_id,
        title="Python开发工程师",
        company="集成测试公司",
        city="兰州",
        detail_url=f"https://example.com/{external_id}",
    )

    try:
        run_job_batch([raw_job], [job])

        connection = connect_postgres()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT b.status, b.row_count, r.payload, j.title
            FROM ops.batches AS b
            JOIN raw.job_records AS r ON r.batch_id = b.id
            JOIN core.jobs AS j
              ON j.source = r.source
             AND j.external_id = r.external_id
            WHERE b.source = %s
              AND r.external_id = %s
            ORDER BY b.id DESC
            LIMIT 1
            """,
            (source, external_id),
        )
        status, row_count, payload, title = cursor.fetchone()
        connection.close()

        assert status == "succeeded"
        assert row_count == 1
        assert payload == raw_job
        assert title == "Python开发工程师"
    finally:
        cleanup = connect_postgres()
        cursor = cleanup.cursor()
        cursor.execute("DELETE FROM raw.job_records WHERE source = %s", (source,))
        cursor.execute("DELETE FROM core.jobs WHERE source = %s", (source,))
        cursor.execute("DELETE FROM ops.batches WHERE source = %s", (source,))
        cleanup.commit()
        cleanup.close()
```

- [ ] **Step 7: Test real raw rollback when core fails**

```python
def test_worker_rolls_back_raw_and_records_failed_batch(monkeypatch):
    from jobflow.workers import jobs as worker_jobs

    external_id = f"worker-failure-{uuid4()}"
    source = "integration_worker_failure"
    raw_job = {"job_id": external_id}
    job = JobRecord(
        source=source,
        external_id=external_id,
        title="Python开发工程师",
        company="集成测试公司",
        city="兰州",
        detail_url=f"https://example.com/{external_id}",
    )

    def failing_insert_jobs(connection, jobs):
        raise RuntimeError("core insert failed")

    monkeypatch.setattr(worker_jobs, "insert_jobs", failing_insert_jobs)

    try:
        with pytest.raises(RuntimeError, match="core insert failed"):
            worker_jobs.run_job_batch([raw_job], [job])

        connection = connect_postgres()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT status, error_message
            FROM ops.batches
            WHERE source = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (source,),
        )
        status, error_message = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) FROM raw.job_records WHERE source = %s",
            (source,),
        )
        raw_count = cursor.fetchone()[0]
        connection.close()

        assert status == "failed"
        assert error_message == "core insert failed"
        assert raw_count == 0
    finally:
        cleanup = connect_postgres()
        cursor = cleanup.cursor()
        cursor.execute("DELETE FROM raw.job_records WHERE source = %s", (source,))
        cursor.execute("DELETE FROM core.jobs WHERE source = %s", (source,))
        cursor.execute("DELETE FROM ops.batches WHERE source = %s", (source,))
        cleanup.commit()
        cleanup.close()
```

- [ ] **Step 8: Run integration and full quality gates**

```cmd
pytest tests\integration\test_postgres_connection.py -q
pytest -q
ruff check .
ruff format --check .
git diff --check
```

Expected: integration tests pass, the full suite reports `53 passed`, Ruff passes, formatting passes, and the diff check is empty.

- [ ] **Step 9: Review and commit**

```cmd
git diff -- tests\integration\test_postgres_connection.py
git add tests\integration\test_postgres_connection.py
git diff --cached
git commit -m "test: 验证 raw 层真实数据库事务"
git status --short --branch
```
