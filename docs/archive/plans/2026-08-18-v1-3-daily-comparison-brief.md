# JobFlow V1.3 Daily Comparison Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an immutable daily job-snapshot pipeline that compares real `AI Agent` job captures day over day and complete natural week over complete natural week, then sends one Chinese management brief followed by one city-share PNG through Telegram.

**Architecture:** Keep `core.jobs` as the current normalized job entity and add immutable daily snapshot headers/items for historical membership. Pure Python comparison modules calculate daily and weekly metrics from snapshot items; a report service loads the relevant snapshots, renders deterministic Chinese text and a Matplotlib PNG, then advances durable Telegram delivery state without duplicating an already-sent message.

**Tech Stack:** Python 3.12, PostgreSQL 18, psycopg 3.2, FastAPI, requests, Matplotlib 3.10, pytest 8.3, Ruff 0.9, Docker Compose, Bash, systemd, Telegram Bot HTTP API.

## Global Constraints

- The only V1.3 search keyword is exactly `AI Agent`.
- Capture exactly Shanghai, Beijing, Hangzhou, and Shenzhen, with `--pages 3` and `--no-detail` for every city.
- All four cities must succeed and return non-empty valid JSON before ETL or report delivery begins.
- Job identity is `(source, external_id)`; a missing item means “not observed in this capture,” never “confirmed offline.”
- Daily comparison is snapshot date D versus natural date D-1; do not substitute an older date.
- Daily and weekly baselines must match keyword, exact city set, pages per city, and detail mode; legacy one-page snapshots cannot baseline V1.3 three-page captures.
- Weekly comparison is emitted only on Sunday and compares two complete Monday-Sunday periods.
- Weekly jobs are deduplicated by `(source, external_id)` and use the last observation in that week for descriptive fields.
- Salary comparison includes only `K_PER_MONTH`; use each range midpoint and then the median.
- Telegram sends text first and PNG second; an image retry must not duplicate successful text.
- The deterministic query brief must work without OpenAI or any external LLM.
- Never print, persist in Git, or include actual passwords, API keys, Bot Tokens, Chat IDs, proxy subscriptions, cookies, private keys, or `.env` values.
- Existing modified README/docs files are user work and must not be overwritten.
- Do not commit or push automatically. Every commit step below is an approval gate and may run only after the user explicitly authorizes it.
- Local checks use `<JOBFLOW_PYTHON>` and `<JOBFLOW_RUFF>`; run them sequentially.

## File Structure

**Create:**

- `migrations/006_add_daily_job_snapshots.sql` — immutable snapshot and delivery-state schema.
- `src/jobflow/models/snapshot.py` — snapshot metadata/items and comparison result value objects.
- `src/jobflow/db/snapshots.py` — snapshot insert/load and delivery-state persistence.
- `src/jobflow/reports/comparison.py` — pure daily and weekly calculations.
- `src/jobflow/reports/daily_brief.py` — management-dashboard Chinese text formatter.
- `src/jobflow/reports/charts.py` — city-share PNG renderer.
- `src/jobflow/reports/daily_service.py` — snapshot loading, calculation, rendering, and idempotent delivery orchestration.
- `src/jobflow/snapshot_backfill.py` — read-only historical audit and explicit verified backfill CLI.
- `tests/db/test_snapshot_migration.py`
- `tests/db/test_snapshots.py`
- `tests/reports/test_comparison.py`
- `tests/reports/test_daily_brief.py`
- `tests/reports/test_charts.py`
- `tests/reports/test_daily_service.py`
- `tests/test_snapshot_backfill.py`

**Modify:**

- `pyproject.toml` — add bounded Matplotlib dependency.
- `Dockerfile` — install a Chinese font and writable Matplotlib cache path.
- `src/jobflow/cli.py` — accept explicit daily-snapshot metadata.
- `src/jobflow/workers/etl.py` — forward optional snapshot metadata.
- `src/jobflow/workers/jobs.py` — insert snapshot data in the successful batch transaction and return `batch_id`.
- `src/jobflow/channels/telegram.py` — return message IDs, add `sendPhoto`, and bounded retries.
- `src/jobflow/api/reports.py` — add protected daily report status/send endpoints while preserving `/reports/cities/send`.
- `ops/daily_update.sh` — expand to three pages, deduplicate merged jobs, resume existing delivery, and call the daily endpoint.
- Existing tests beside every modified module.
- `README.md`, `docs/reference/architecture.md`, `docs/project-handoff.md`, and `docs/guides/ubuntu-deployment.md` only after real implementation evidence exists.

---

### Task 1: Add Immutable Snapshot and Delivery Tables

**Files:**

- Create: `migrations/006_add_daily_job_snapshots.sql`
- Create: `tests/db/test_snapshot_migration.py`
- Test: `tests/integration/test_postgres_connection.py`

**Interfaces:**

- Produces: `core.job_snapshots`, `core.job_snapshot_items`, and `ops.report_deliveries`.
- Enforces: one formal snapshot per `(snapshot_date, search_keyword)` and one item per `(snapshot_id, source, external_id)`.

- [ ] **Step 1: Write the failing migration contract test**

```python
from pathlib import Path


def test_snapshot_migration_defines_immutable_history_and_delivery_state() -> None:
    sql = Path("migrations/006_add_daily_job_snapshots.sql").read_text(encoding="utf-8")
    normalized = " ".join(sql.split())

    assert "CREATE TABLE IF NOT EXISTS core.job_snapshots" in normalized
    assert "UNIQUE (snapshot_date, search_keyword)" in normalized
    assert "batch_id BIGINT NOT NULL UNIQUE" in normalized
    assert "cities TEXT[] NOT NULL" in normalized
    assert "details_included BOOLEAN NOT NULL" in normalized
    assert "CREATE TABLE IF NOT EXISTS core.job_snapshot_items" in normalized
    assert "PRIMARY KEY (snapshot_id, source, external_id)" in normalized
    assert "CREATE TABLE IF NOT EXISTS ops.report_deliveries" in normalized
    assert "partial_failed" in normalized
    assert "text_message_id BIGINT" in normalized
    assert "photo_message_id BIGINT" in normalized
```

- [ ] **Step 2: Run the test and verify the missing migration failure**

Run:

```powershell
<JOBFLOW_PYTHON> -m pytest tests/db/test_snapshot_migration.py -q
```

Expected: FAIL because `migrations/006_add_daily_job_snapshots.sql` does not exist.

- [ ] **Step 3: Create the migration with exact constraints and indexes**

```sql
CREATE TABLE IF NOT EXISTS core.job_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    search_keyword TEXT NOT NULL,
    batch_id BIGINT NOT NULL UNIQUE REFERENCES ops.batches (id),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    city_count SMALLINT NOT NULL,
    cities TEXT[] NOT NULL,
    pages_per_city SMALLINT NOT NULL,
    details_included BOOLEAN NOT NULL,
    status TEXT NOT NULL DEFAULT 'succeeded',
    CONSTRAINT job_snapshots_date_keyword_key UNIQUE (snapshot_date, search_keyword),
    CONSTRAINT job_snapshots_city_count_check CHECK (city_count > 0),
    CONSTRAINT job_snapshots_cities_check CHECK (city_count = cardinality(cities)),
    CONSTRAINT job_snapshots_pages_check CHECK (pages_per_city > 0),
    CONSTRAINT job_snapshots_status_check CHECK (status = 'succeeded')
);

CREATE TABLE IF NOT EXISTS core.job_snapshot_items (
    snapshot_id BIGINT NOT NULL REFERENCES core.job_snapshots (id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    city TEXT NOT NULL,
    salary_text TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_unit TEXT,
    salary_months SMALLINT,
    skills TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_id, source, external_id)
);

CREATE INDEX IF NOT EXISTS job_snapshots_keyword_date_idx
    ON core.job_snapshots (search_keyword, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS job_snapshot_items_snapshot_city_idx
    ON core.job_snapshot_items (snapshot_id, city);

CREATE TABLE IF NOT EXISTS ops.report_deliveries (
    snapshot_id BIGINT PRIMARY KEY REFERENCES core.job_snapshots (id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    text_message_id BIGINT,
    photo_message_id BIGINT,
    text_attempts SMALLINT NOT NULL DEFAULT 0,
    photo_attempts SMALLINT NOT NULL DEFAULT 0,
    last_error_type TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT report_deliveries_status_check CHECK (
        status IN ('pending', 'text_sent', 'completed', 'partial_failed', 'failed')
    ),
    CONSTRAINT report_deliveries_attempts_check CHECK (
        text_attempts >= 0 AND photo_attempts >= 0
    )
);
```

- [ ] **Step 4: Add a real PostgreSQL integration assertion**

```python
def test_snapshot_uniqueness_in_real_postgres(postgres_connection) -> None:
    source = f"integration_snapshot_{uuid4()}"
    batch_id = start_batch(postgres_connection, source)
    finish_batch(postgres_connection, batch_id=batch_id, row_count=1)
    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        INSERT INTO core.job_snapshots
            (snapshot_date, search_keyword, batch_id, city_count, cities, pages_per_city, details_included)
        VALUES (%s, %s, %s, 4, %s, 3, FALSE)
        RETURNING id
        """,
        (date(2026, 8, 18), source, batch_id, ["上海", "北京", "杭州", "深圳"]),
    )
    snapshot_id = cursor.fetchone()[0]
    cursor.execute(
        """
        INSERT INTO core.job_snapshot_items
            (snapshot_id, source, external_id, title, company, city)
        VALUES (%s, %s, 'job-1', '测试岗位', '测试公司', '上海')
        """,
        (snapshot_id, source),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        cursor.execute(
            """
            INSERT INTO core.job_snapshot_items
                (snapshot_id, source, external_id, title, company, city)
            VALUES (%s, %s, 'job-1', '重复岗位', '测试公司', '上海')
            """,
            (snapshot_id, source),
        )
```

The existing `postgres_connection` fixture rollback removes the test rows. Add a second transaction in the same file that attempts another snapshot with the same `(date, keyword)` and asserts `UniqueViolation`.

- [ ] **Step 5: Run migration and database tests**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/db/test_snapshot_migration.py tests/integration/test_postgres_connection.py -q
```

Expected: PASS; the integration test may be skipped only when the documented local PostgreSQL test environment is intentionally unavailable.

- [ ] **Step 6: Approval-gated commit**

```powershell
git add migrations/006_add_daily_job_snapshots.sql tests/db/test_snapshot_migration.py tests/integration/test_postgres_connection.py
git commit -m "feat: add immutable daily job snapshots"
```

Do not run these commands until the user explicitly authorizes this commit.

### Task 2: Persist Snapshot Metadata and Items in the ETL Success Transaction

**Files:**

- Create: `src/jobflow/models/snapshot.py`
- Create: `src/jobflow/db/snapshots.py`
- Create: `tests/db/test_snapshots.py`
- Modify: `src/jobflow/workers/jobs.py`
- Modify: `src/jobflow/workers/etl.py`
- Modify: `src/jobflow/cli.py`
- Modify: `tests/workers/test_worker_jobs.py`
- Modify: `tests/workers/test_etl.py`
- Modify: `tests/test_cli.py`

**Interfaces:**

- Produces: `SnapshotMetadata(snapshot_date, search_keyword, cities, pages_per_city, details_included)` with derived `city_count`.
- Produces: `insert_snapshot(connection, *, batch_id, metadata, jobs) -> int`.
- Changes: `run_job_batch(raw_jobs: list[dict[str, str]], jobs: list[JobRecord], snapshot_metadata: SnapshotMetadata | None = None) -> int | None`.
- Preserves: manual ETL without metadata still updates raw/core and creates no daily snapshot.

- [ ] **Step 1: Write failing model, repository, worker, and CLI tests**

```python
from datetime import date

from jobflow.models.snapshot import SnapshotMetadata


def test_snapshot_metadata_rejects_invalid_scope() -> None:
    with pytest.raises(ValueError, match="cities"):
        SnapshotMetadata(date(2026, 8, 18), "AI Agent", (), 3, False)


def test_cli_forwards_explicit_snapshot_metadata(monkeypatch) -> None:
    received = []
    monkeypatch.setattr(cli, "run_boss_snapshot", lambda path, metadata=None: received.append((path, metadata)))

    result = cli.main([
        "snapshot.json",
        "--snapshot-date", "2026-08-18",
        "--search-keyword", "AI Agent",
        "--cities", "上海,北京,杭州,深圳",
        "--pages-per-city", "3",
        "--detail-mode", "no-detail",
    ])

    assert result == 0
    assert received[0][1] == SnapshotMetadata(
        date(2026, 8, 18),
        "AI Agent",
        ("上海", "北京", "杭州", "深圳"),
        3,
        False,
    )
```

Add worker assertions that `insert_snapshot` occurs after raw/core inserts and before `finish_batch`, and that an `insert_snapshot` failure rolls back raw/core/snapshot work before the existing failed-batch record is committed.

- [ ] **Step 2: Verify tests fail before implementation**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/db/test_snapshots.py tests/workers/test_worker_jobs.py tests/workers/test_etl.py tests/test_cli.py -q
```

Expected: FAIL because `jobflow.models.snapshot`, `jobflow.db.snapshots`, and CLI options do not exist.

- [ ] **Step 3: Add the immutable metadata value object**

```python
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_date: date
    search_keyword: str
    cities: tuple[str, ...]
    pages_per_city: int
    details_included: bool

    @property
    def city_count(self) -> int:
        return len(self.cities)

    def __post_init__(self) -> None:
        if not self.search_keyword.strip():
            raise ValueError("search_keyword must not be empty")
        if not self.cities or len(set(self.cities)) != len(self.cities):
            raise ValueError("cities must be non-empty and unique")
        if self.pages_per_city <= 0:
            raise ValueError("pages_per_city must be positive")
```

- [ ] **Step 4: Implement snapshot insertion using normalized `JobRecord` values**

```python
def insert_snapshot(connection, *, batch_id: int, metadata: SnapshotMetadata, jobs: list[JobRecord]) -> int:
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO core.job_snapshots
            (snapshot_date, search_keyword, batch_id, city_count, cities, pages_per_city, details_included)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            metadata.snapshot_date,
            metadata.search_keyword,
            batch_id,
            metadata.city_count,
            list(metadata.cities),
            metadata.pages_per_city,
            metadata.details_included,
        ),
    )
    snapshot_id = cursor.fetchone()[0]
    for job in jobs:
        cursor.execute(
            """
            INSERT INTO core.job_snapshot_items (
                snapshot_id, source, external_id, title, company, city,
                salary_text, salary_min, salary_max, salary_unit, salary_months, skills
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                snapshot_id, job.source, job.external_id, job.title, job.company, job.city,
                job.salary_text, job.salary_min, job.salary_max, job.salary_unit,
                job.salary_months, job.skills,
            ),
        )
    cursor.execute(
        "INSERT INTO ops.report_deliveries (snapshot_id) VALUES (%s)",
        (snapshot_id,),
    )
    return snapshot_id
```

- [ ] **Step 5: Thread optional metadata through CLI and worker**

Add all four CLI flags as an all-or-none group. Parse the date with `date.fromisoformat`. Change `run_boss_snapshot(path, metadata=None)` to forward metadata. Change `run_job_batch` to return its batch ID and call `insert_snapshot` before `finish_batch` when metadata is present. Preserve the first commit after `start_batch` so a later rollback can still mark that batch failed.

The success event order with metadata must be:

```text
start_batch → commit running batch → insert_raw_jobs → insert_jobs
→ insert_snapshot → finish_batch → commit → close
```

- [ ] **Step 6: Run focused tests and Ruff**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/db/test_snapshots.py tests/workers/test_worker_jobs.py tests/workers/test_etl.py tests/test_cli.py -q
<JOBFLOW_RUFF> check src/jobflow/models/snapshot.py src/jobflow/db/snapshots.py src/jobflow/workers src/jobflow/cli.py tests/db/test_snapshots.py tests/workers tests/test_cli.py
```

Expected: all focused tests PASS and Ruff reports no errors.

- [ ] **Step 7: Approval-gated commit**

```powershell
git add src/jobflow/models/snapshot.py src/jobflow/db/snapshots.py src/jobflow/workers/jobs.py src/jobflow/workers/etl.py src/jobflow/cli.py tests/db/test_snapshots.py tests/workers/test_worker_jobs.py tests/workers/test_etl.py tests/test_cli.py
git commit -m "feat: persist daily snapshot membership"
```

### Task 3: Implement Pure Daily Comparison Calculations

**Files:**

- Modify: `src/jobflow/models/snapshot.py`
- Create: `src/jobflow/reports/comparison.py`
- Create: `tests/reports/test_comparison.py`

**Interfaces:**

- Produces: `SnapshotItem`, `MetricChange`, `NamedMetric`, and `DailyComparison` frozen dataclasses.
- Produces: `compare_daily(current, previous, *, cities, skill_limit=5) -> DailyComparison`.
- Consumes: normalized snapshot items, never cumulative `core.jobs` rows.

- [ ] **Step 1: Write failing daily-comparison examples**

Create test items with identities `a`, `b`, `c`, and `d` so current contains `a,b,c`, previous contains `a,b,d`. Assert:

```python
comparison = compare_daily(current, previous, cities=("上海", "北京", "杭州", "深圳"))

assert comparison.total == MetricChange(current=3, previous=3, delta=0, percent=Decimal("0.0"))
assert comparison.new_count == 1
assert comparison.continued_count == 2
assert comparison.missing_count == 1
assert comparison.city_metrics[0].name == "上海"
assert comparison.salary_midpoint_median.current == Decimal("25")
assert comparison.skills[0].name == "Python"
```

Use a parametrized edge-case table with these exact expected outcomes:

```python
@pytest.mark.parametrize(
    ("current", "previous", "expected_percent", "expected_salary"),
    [
        (items(2), None, None, Decimal("20")),
        (items(2), items(0), None, Decimal("20")),
        (monthly_items((10, 20), (20, 30)), monthly_items((10, 20)), Decimal("100.0"), Decimal("20")),
        (non_monthly_items(), non_monthly_items(), Decimal("0.0"), None),
    ],
)
def test_daily_comparison_edge_cases(current, previous, expected_percent, expected_salary) -> None:
    result = compare_daily(current, previous, cities=("上海", "北京", "杭州", "深圳"))
    assert result.total.percent == expected_percent
    assert result.salary_midpoint_median.current == expected_salary
```

In the duplicate-skill fixture use `skills=("Python", "Python")` and assert Python’s current job count is 1. Assert `tuple(metric.name for metric in result.city_metrics)` equals the configured four-city order.

- [ ] **Step 2: Run the tests and verify missing comparison types**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_comparison.py -q
```

Expected: FAIL on missing imports from `jobflow.reports.comparison`.

- [ ] **Step 3: Define exact immutable result types**

```python
@dataclass(frozen=True)
class SnapshotItem:
    source: str
    external_id: str
    title: str
    company: str
    city: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_unit: str | None = None
    skills: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, str]:
        return self.source, self.external_id


@dataclass(frozen=True)
class MetricChange:
    current: int | Decimal | None
    previous: int | Decimal | None
    delta: int | Decimal | None
    percent: Decimal | None


@dataclass(frozen=True)
class NamedMetric:
    name: str
    change: MetricChange


@dataclass(frozen=True)
class DailyComparison:
    has_baseline: bool
    total: MetricChange
    city_metrics: tuple[NamedMetric, ...]
    new_count: int | None
    continued_count: int | None
    missing_count: int | None
    skills: tuple[NamedMetric, ...]
    salary_midpoint_median: MetricChange
```

- [ ] **Step 4: Implement identity-set, skill, salary, and percent helpers**

Use `Decimal` for percent and salary output. Build one dictionary per snapshot keyed by `item.identity`; reject duplicate identities with `ValueError`. Count each normalized skill at most once per job. Include salary only when unit is `K_PER_MONTH`, both bounds exist, and maximum is not below minimum. Use `statistics.median` over `Decimal((min + max) / 2)` values.

`percent` is `None` when no baseline or the previous value is zero. Quantize non-null percentages to one decimal place with `Decimal("0.1")`.

- [ ] **Step 5: Run comparison tests**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_comparison.py -q
<JOBFLOW_RUFF> check src/jobflow/models/snapshot.py src/jobflow/reports/comparison.py tests/reports/test_comparison.py
```

Expected: all daily-comparison tests PASS.

- [ ] **Step 6: Approval-gated commit**

```powershell
git add src/jobflow/models/snapshot.py src/jobflow/reports/comparison.py tests/reports/test_comparison.py
git commit -m "feat: calculate daily snapshot comparisons"
```

### Task 4: Add Complete Natural-Week Comparison

**Files:**

- Modify: `src/jobflow/models/snapshot.py`
- Modify: `src/jobflow/reports/comparison.py`
- Modify: `tests/reports/test_comparison.py`

**Interfaces:**

- Produces: `DatedSnapshot(snapshot_date, items)` and `WeeklyComparison`.
- Produces: `compare_complete_weeks(*, report_date, current_days, previous_days, cities, skill_limit=5) -> WeeklyComparison | None`.
- Returns `None` on Monday-Saturday or when either Monday-Sunday period lacks any natural date.

- [ ] **Step 1: Write failing Sunday, missing-day, and last-observation tests**

```python
result = compare_complete_weeks(
    report_date=date(2026, 8, 23),
    current_days=current_seven_days,
    previous_days=previous_seven_days,
    cities=("上海", "北京", "杭州", "深圳"),
)

assert result is not None
assert result.current_range == (date(2026, 8, 17), date(2026, 8, 23))
assert result.previous_range == (date(2026, 8, 10), date(2026, 8, 16))
assert result.total.current == 2
```

Make one job appear on all seven days and assert it counts once. Change its salary and skill on Sunday and assert weekly descriptive metrics use Sunday’s last observation. Remove Wednesday and assert `None`. Set `report_date` to Saturday and assert `None`. Include a week crossing December to January.

- [ ] **Step 2: Run the tests and verify weekly behavior is missing**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_comparison.py -q
```

Expected: the new weekly tests FAIL.

- [ ] **Step 3: Implement complete-week validation and last-observation deduplication**

```python
def _week_dates(sunday: date) -> tuple[date, ...]:
    monday = sunday - timedelta(days=6)
    return tuple(monday + timedelta(days=offset) for offset in range(7))


def _collapse_week(days: Sequence[DatedSnapshot]) -> tuple[SnapshotItem, ...]:
    latest: dict[tuple[str, str], tuple[date, SnapshotItem]] = {}
    for day in sorted(days, key=lambda value: value.snapshot_date):
        for item in day.items:
            latest[item.identity] = (day.snapshot_date, item)
    return tuple(value[1] for value in latest.values())
```

Validate the exact seven expected dates for both periods. Reuse the same count, city, skill, and salary helpers as daily comparison so the two modes cannot drift.

- [ ] **Step 4: Run all comparison tests and Ruff**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_comparison.py -q
<JOBFLOW_RUFF> check src/jobflow/models/snapshot.py src/jobflow/reports/comparison.py tests/reports/test_comparison.py
```

Expected: daily and weekly comparison tests PASS, including incomplete-week rejection.

- [ ] **Step 5: Approval-gated commit**

```powershell
git add src/jobflow/models/snapshot.py src/jobflow/reports/comparison.py tests/reports/test_comparison.py
git commit -m "feat: compare complete natural weeks"
```

### Task 5: Load Snapshot History for Report Generation

**Files:**

- Modify: `src/jobflow/db/snapshots.py`
- Modify: `tests/db/test_snapshots.py`

**Interfaces:**

- Produces: `get_snapshot(connection, *, snapshot_date, search_keyword) -> SnapshotHeader | None`.
- Produces: `list_snapshot_items(connection, snapshot_id) -> tuple[SnapshotItem, ...]`.
- Produces: `list_dated_snapshots(connection, *, start_date, end_date, search_keyword) -> tuple[DatedSnapshot, ...]`.
- Produces: `get_delivery(connection, snapshot_id) -> ReportDelivery` and explicit delivery-state update functions.

- [ ] **Step 1: Write SQL-mapping tests with fake cursor rows**

```python
def test_get_snapshot_filters_by_exact_natural_date_and_keyword() -> None:
    connection = FakeConnection([
        (17, date(2026, 8, 18), "AI Agent", 42, 4, ["上海", "北京", "杭州", "深圳"], 3, False),
    ])

    result = get_snapshot(
        connection,
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
    )

    sql, params = connection.cursor_instance.executed[0]
    assert "snapshot_date = %s" in sql
    assert "search_keyword = %s" in sql
    assert params == (date(2026, 8, 18), "AI Agent")
    assert result.id == 17


def test_list_snapshot_items_maps_skills_to_tuple() -> None:
    connection = FakeConnection([
        ("boss_zhipin", "job-1", "算法工程师", "示例公司", "上海", 20, 30, "K_PER_MONTH", ["Python", "RAG"]),
    ])

    result = list_snapshot_items(connection, 17)

    assert result[0].identity == ("boss_zhipin", "job-1")
    assert result[0].skills == ("Python", "RAG")
```

Include a grouping test whose fake rows contain two dates and whose exact assertion is:

```python
assert [day.snapshot_date for day in result] == [date(2026, 8, 17), date(2026, 8, 18)]
```

Do not synthesize a missing natural date in this repository function.

- [ ] **Step 2: Run the repository tests and confirm missing functions**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/db/test_snapshots.py -q
```

Expected: FAIL on missing load and delivery functions.

- [ ] **Step 3: Add frozen header and delivery value objects**

```python
@dataclass(frozen=True)
class SnapshotHeader:
    id: int
    snapshot_date: date
    search_keyword: str
    batch_id: int
    city_count: int
    cities: tuple[str, ...]
    pages_per_city: int
    details_included: bool


@dataclass(frozen=True)
class ReportDelivery:
    snapshot_id: int
    status: str
    text_message_id: int | None
    photo_message_id: int | None
    text_attempts: int
    photo_attempts: int
    last_error_type: str | None
```

- [ ] **Step 4: Implement exact read and state-transition queries**

Add narrow functions rather than exposing arbitrary status strings:

```python
def _update_delivery(connection, snapshot_id: int, *, status: str, message_column: str | None,
                     message_id: int | None, attempts_column: str, attempts: int,
                     error_type: str | None) -> None:
    allowed_columns = {"text_message_id", "photo_message_id", "text_attempts", "photo_attempts"}
    if attempts_column not in allowed_columns or (message_column and message_column not in allowed_columns):
        raise ValueError("unsupported delivery column")
    assignments = ["status = %s", f"{attempts_column} = %s", "last_error_type = %s", "updated_at = CURRENT_TIMESTAMP"]
    params: list[object] = [status, attempts, error_type]
    if message_column is not None:
        assignments.insert(1, f"{message_column} = %s")
        params.insert(1, message_id)
    params.append(snapshot_id)
    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE ops.report_deliveries SET {', '.join(assignments)} WHERE snapshot_id = %s",
        tuple(params),
    )


def record_text_sent(connection, snapshot_id: int, message_id: int, attempts: int) -> None:
    _update_delivery(connection, snapshot_id, status="text_sent", message_column="text_message_id",
                     message_id=message_id, attempts_column="text_attempts", attempts=attempts,
                     error_type=None)


def record_photo_sent(connection, snapshot_id: int, message_id: int, attempts: int) -> None:
    _update_delivery(connection, snapshot_id, status="completed", message_column="photo_message_id",
                     message_id=message_id, attempts_column="photo_attempts", attempts=attempts,
                     error_type=None)


def record_text_failure(connection, snapshot_id: int, error_type: str, attempts: int) -> None:
    _update_delivery(connection, snapshot_id, status="failed", message_column=None,
                     message_id=None, attempts_column="text_attempts", attempts=attempts,
                     error_type=error_type)


def record_photo_failure(connection, snapshot_id: int, error_type: str, attempts: int) -> None:
    _update_delivery(connection, snapshot_id, status="partial_failed", message_column=None,
                     message_id=None, attempts_column="photo_attempts", attempts=attempts,
                     error_type=error_type)
```

- [ ] **Step 5: Verify mapping and transition tests**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/db/test_snapshots.py -q
<JOBFLOW_RUFF> check src/jobflow/db/snapshots.py src/jobflow/models/snapshot.py tests/db/test_snapshots.py
```

Expected: PASS with SQL parameters asserted by tests.

- [ ] **Step 6: Approval-gated commit**

```powershell
git add src/jobflow/db/snapshots.py src/jobflow/models/snapshot.py tests/db/test_snapshots.py
git commit -m "feat: load snapshot history and delivery state"
```

### Task 6: Render the Approved Chinese Management Brief

**Files:**

- Create: `src/jobflow/reports/daily_brief.py`
- Create: `tests/reports/test_daily_brief.py`

**Interfaces:**

- Produces: `build_daily_brief(*, report_date, keyword, city_count, pages_per_city, daily, weekly=None) -> str`.
- Consumes: `DailyComparison` and optional `WeeklyComparison` from Task 3/4.
- Guarantees: deterministic Chinese plain text with length at most 4096 characters.

- [ ] **Step 1: Write a full approved-format golden test**

```python
def test_build_daily_brief_uses_management_dashboard_order() -> None:
    report = build_daily_brief(
        report_date=date(2026, 8, 18),
        keyword="AI Agent",
        city_count=4,
        pages_per_city=3,
        daily=daily_fixture(),
    )

    assert report.startswith("━━━━━━━━━━━━━━━━━━\nJobFlow｜AI Agent 招聘市场日报")
    assert report.index("【今日概览】") < report.index("【管理摘要】")
    assert report.index("【管理摘要】") < report.index("【城市表现】")
    assert report.index("【城市表现】") < report.index("【岗位快照变化】")
    assert report.index("【岗位快照变化】") < report.index("【热门技能】")
    assert "范围：4 城市 × 每城 3 页" in report
    assert "本次未出现不代表岗位已经下线" in report
    assert len(report) <= 4096
```

Use one parametrized direction test:

```python
@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (MetricChange(12, 10, 2, Decimal("20.0")), "↑ 2个（↑ 20.0%）"),
        (MetricChange(8, 10, -2, Decimal("-20.0")), "↓ 2个（↓ 20.0%）"),
        (MetricChange(10, 10, 0, Decimal("0.0")), "持平"),
        (MetricChange(10, None, None, None), "暂无历史基准"),
    ],
)
def test_format_direction(change, expected) -> None:
    assert _format_direction(change) == expected
```

The no-salary fixture must produce “暂无有效月薪样本”. A Sunday fixture must contain `【本周趋势`; the same data with a Tuesday report date must not contain that heading.

- [ ] **Step 2: Run the formatter tests and verify the module is missing**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_daily_brief.py -q
```

Expected: FAIL because `daily_brief.py` does not exist.

- [ ] **Step 3: Implement formatting helpers and strict output limit**

```python
TELEGRAM_MESSAGE_LIMIT = 4096


def _format_direction(change: MetricChange, *, unit: str = "个") -> str:
    if change.previous is None or change.delta is None:
        return "暂无历史基准"
    if change.delta == 0:
        return "持平"
    arrow = "↑" if change.delta > 0 else "↓"
    amount = abs(change.delta)
    if change.percent is None:
        return f"{arrow} {amount}{unit}（比例不适用）"
    return f"{arrow} {amount}{unit}（{arrow} {abs(change.percent):.1f}%）"


def _validate_length(report: str) -> str:
    if len(report) > TELEGRAM_MESSAGE_LIMIT:
        raise ValueError("daily brief exceeds Telegram message limit")
    return report
```

Build every section from explicit line lists. The management summary may state only: total up/down/flat, city with largest absolute positive delta, and top skill by current job count. If no baseline exists, describe only current distribution facts.

- [ ] **Step 4: Verify formatter output**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_daily_brief.py -q
<JOBFLOW_RUFF> check src/jobflow/reports/daily_brief.py tests/reports/test_daily_brief.py
```

Expected: PASS; no test relies on terminal color or Telegram `parse_mode`.

- [ ] **Step 5: Approval-gated commit**

```powershell
git add src/jobflow/reports/daily_brief.py tests/reports/test_daily_brief.py
git commit -m "feat: render management dashboard brief"
```

### Task 7: Generate a Chinese City-Share PNG

**Files:**

- Modify: `pyproject.toml`
- Modify: `Dockerfile`
- Create: `src/jobflow/reports/charts.py`
- Create: `tests/reports/test_charts.py`

**Interfaces:**

- Produces: `build_city_share_png(city_metrics: Sequence[NamedMetric]) -> bytes`.
- Raises: `ValueError` for empty totals, negative counts, or duplicate city names.
- Output: valid square PNG bytes suitable for Telegram multipart upload.

- [ ] **Step 1: Write failing PNG signature and validation tests**

```python
def test_build_city_share_png_returns_valid_png() -> None:
    image = build_city_share_png(city_metrics_fixture())

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10_000


def test_build_city_share_png_rejects_zero_total() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_city_share_png(zero_city_metrics_fixture())
```

The axes-spy test must assert:

```python
build_city_share_png(city_metrics_fixture())
assert pie_spy.call_args.args[0] == [82, 76, 63, 65]
assert pie_spy.call_args.kwargs["labels"] == ["上海", "北京", "杭州", "深圳"]
assert legend_spy.call_args.args[1] == ["上海：82 个", "北京：76 个", "杭州：63 个", "深圳：65 个"]
```

- [ ] **Step 2: Add the bounded dependency and verify the test initially fails**

Add to project dependencies:

```toml
"matplotlib>=3.10,<4",
```

Run:

```powershell
<JOBFLOW_PYTHON> -m pip install -e ".[dev]"
<JOBFLOW_PYTHON> -m pytest tests/reports/test_charts.py -q
```

Expected: dependency installation succeeds; test FAILS because `build_city_share_png` is missing.

- [ ] **Step 3: Implement an in-memory Agg renderer**

```python
from io import BytesIO
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from jobflow.models.snapshot import NamedMetric


def build_city_share_png(city_metrics: Sequence[NamedMetric]) -> bytes:
    labels = [metric.name for metric in city_metrics]
    values = [int(metric.change.current or 0) for metric in city_metrics]
    if len(labels) != len(set(labels)):
        raise ValueError("city names must be unique")
    if any(value < 0 for value in values) or sum(values) <= 0:
        raise ValueError("city total must be positive")

    matplotlib.rcParams["font.family"] = ["Noto Sans CJK SC"]
    colors = ("#2563EB", "#7C3AED", "#059669", "#D97706")
    legend = [f"{label}：{value} 个" for label, value in zip(labels, values)]
    fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
    wedges, _, _ = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors[: len(values)],
    )
    ax.legend(wedges, legend, loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=2)
    ax.set_title("AI Agent 当日城市岗位占比")
    ax.axis("equal")
    output = BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output.getvalue()
```

- [ ] **Step 4: Make the container capable of rendering Chinese text**

Before creating the non-root user in `Dockerfile`, install `fonts-noto-cjk` and remove apt lists. Add `ENV MPLCONFIGDIR=/tmp/jobflow-matplotlib`, create that directory, and give it to the `jobflow` user before `USER jobflow`. Do not run the API as root.

- [ ] **Step 5: Run local tests and build the API image**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_charts.py -q
<JOBFLOW_RUFF> check src/jobflow/reports/charts.py tests/reports/test_charts.py
docker compose build api
```

Expected: chart tests PASS; Docker build installs Matplotlib and Chinese fonts without exposing secrets.

- [ ] **Step 6: Approval-gated commit**

```powershell
git add pyproject.toml Dockerfile src/jobflow/reports/charts.py tests/reports/test_charts.py
git commit -m "feat: render city share chart"
```

### Task 8: Add Telegram Photo Upload, Message IDs, and Bounded Retry

**Files:**

- Modify: `src/jobflow/channels/telegram.py`
- Modify: `tests/channels/test_telegram.py`

**Interfaces:**

- Produces: `TelegramReceipt(message_id: int, attempts: int)`.
- Changes: `send_telegram_text(report: str, *, bot_token: str | None = None, chat_id: str | None = None, post=None, sleep=time.sleep, max_attempts: int = 3) -> TelegramReceipt`.
- Produces: `send_telegram_photo(photo: bytes, *, filename: str = "jobflow-city-share.png", bot_token: str | None = None, chat_id: str | None = None, post=None, sleep=time.sleep, max_attempts: int = 3) -> TelegramReceipt`.
- Both functions accept injected `post`, `sleep`, and `max_attempts=3` for deterministic tests.

- [ ] **Step 1: Write failing message-ID, multipart, and retry tests**

```python
def test_send_telegram_photo_uploads_png_and_returns_message_id() -> None:
    response = telegram_ok_response(message_id=27)
    post = Mock(return_value=response)

    receipt = send_telegram_photo(
        b"\x89PNG\r\n\x1a\nimage",
        bot_token="bot-token",
        chat_id="12345",
        post=post,
        sleep=Mock(),
    )

    assert receipt == TelegramReceipt(message_id=27, attempts=1)
    _, kwargs = post.call_args
    assert kwargs["data"] == {"chat_id": "12345"}
    assert kwargs["files"]["photo"][0] == "jobflow-city-share.png"


def test_send_telegram_photo_retries_5xx_three_times() -> None:
    post = Mock(side_effect=[server_error_response(), server_error_response(), telegram_ok_response(9)])
    sleep = Mock()

    assert send_telegram_photo(PNG_BYTES, bot_token="bot-token", chat_id="1", post=post, sleep=sleep) == TelegramReceipt(9, 3)
    assert post.call_count == 3
    assert sleep.call_count == 2
```

The retry safety tests must include:

```python
assert unauthorized_post.call_count == 1
assert timeout_then_success_post.call_count == 2
assert send_telegram_text("报告", bot_token="bot-token", chat_id="1", post=ok_post, sleep=Mock()) == TelegramReceipt(7, 1)
assert "secret-bot-token" not in str(exc_info.value)
assert "secret response detail" not in str(exc_info.value)
```

A malformed `{ "ok": True, "result": {} }` payload must raise `TelegramDeliveryError`.

- [ ] **Step 2: Run the channel tests and confirm missing behavior**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/channels/test_telegram.py -q
```

Expected: FAIL because text returns `None`, `send_telegram_photo` is missing, and retry is absent.

- [ ] **Step 3: Implement one private request/retry helper**

```python
@dataclass(frozen=True)
class TelegramReceipt:
    message_id: int
    attempts: int


class TelegramDeliveryError(Exception):
    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


def _request_telegram(*, request, max_attempts: int, sleep) -> TelegramReceipt:
    for attempt in range(1, max_attempts + 1):
        try:
            response = request()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_attempts:
                    sleep(attempt)
                    continue
            if 400 <= response.status_code < 500:
                raise TelegramDeliveryError("Telegram request rejected", attempts=attempt)
            response.raise_for_status()
            payload = response.json()
            message_id = payload.get("result", {}).get("message_id") if isinstance(payload, dict) else None
            if not isinstance(payload, dict) or payload.get("ok") is not True or not isinstance(message_id, int):
                raise TelegramDeliveryError("Telegram rejected message")
            return TelegramReceipt(message_id=message_id, attempts=attempt)
        except requests.RequestException as exc:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryError("Telegram request failed", attempts=attempt) from exc
    raise TelegramDeliveryError("Telegram request failed", attempts=max_attempts)
```

Wrap request creation in zero-argument closures so text uses JSON and photo uses multipart `data` plus `files`. Validate PNG magic bytes before any request. Keep the existing 4096-character check.

- [ ] **Step 4: Run all channel tests and Ruff**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/channels/test_telegram.py tests/channels/test_wecom.py -q
<JOBFLOW_RUFF> check src/jobflow/channels tests/channels
```

Expected: all Telegram and WeCom tests PASS; tokens remain absent from exception strings.

- [ ] **Step 5: Approval-gated commit**

```powershell
git add src/jobflow/channels/telegram.py tests/channels/test_telegram.py
git commit -m "feat: send Telegram report images safely"
```

### Task 9: Orchestrate Idempotent Daily Report Delivery and API Endpoints

**Files:**

- Create: `src/jobflow/reports/daily_service.py`
- Create: `tests/reports/test_daily_service.py`
- Modify: `src/jobflow/api/reports.py`
- Modify: `tests/api/test_reports.py`

**Interfaces:**

- Produces: `get_daily_report_status(connection, *, snapshot_date, keyword) -> dict[str, object]`.
- Produces: `send_daily_report(connection, *, snapshot_date: date, keyword: str, text_sender=send_telegram_text, photo_sender=send_telegram_photo) -> dict[str, object]`.
- Adds: protected `GET /reports/daily/status` and `POST /reports/daily/send`.
- Preserves: existing `/reports/cities/send?mode=query|ai` behavior.

- [ ] **Step 1: Write failing service tests for every delivery state**

```python
def test_send_daily_report_sends_text_then_photo_and_records_ids(monkeypatch) -> None:
    events = []
    text_sender = Mock(side_effect=lambda text: events.append("text") or TelegramReceipt(101, 1))
    photo_sender = Mock(side_effect=lambda image: events.append("photo") or TelegramReceipt(202, 1))

    result = send_daily_report(
        connection_fixture(status="pending"),
        snapshot_date=date(2026, 8, 18),
        keyword="AI Agent",
        text_sender=text_sender,
        photo_sender=photo_sender,
    )

    assert events == ["text", "photo"]
    assert result["status"] == "sent"
    assert result["text_message_id"] == 101
    assert result["photo_message_id"] == 202


def test_send_daily_report_resumes_photo_without_duplicate_text() -> None:
    text_sender = Mock()
    photo_sender = Mock(return_value=TelegramReceipt(303, 1))

    result = send_daily_report(
        connection_fixture(status="partial_failed", text_message_id=101),
        snapshot_date=date(2026, 8, 18),
        keyword="AI Agent",
        text_sender=text_sender,
        photo_sender=photo_sender,
    )

    text_sender.assert_not_called()
    photo_sender.assert_called_once()
    assert result["status"] == "sent"
```

The remaining named tests and their exact assertions are:

| Test | Setup | Required assertion |
| --- | --- | --- |
| `test_missing_snapshot_raises_not_found` | `get_snapshot` returns `None` | raises `DailySnapshotNotFound` and neither sender is called |
| `test_completed_delivery_returns_already_sent_without_external_calls` | delivery status is `completed` | result status is `already_sent`; neither formatter, chart, nor sender is called |
| `test_chart_failure_prevents_text_send` | chart renderer raises `ValueError` | text sender and photo sender are both untouched |
| `test_text_failure_records_failed_and_commits` | text sender raises `TelegramDeliveryError` | `record_text_failure` and one commit occur; photo sender is untouched |
| `test_photo_failure_records_partial_failed_and_commits` | text returns 101 and photo raises | `record_text_sent`, then `record_photo_failure`, with one commit after each transition |
| `test_missing_previous_natural_day_does_not_load_older_snapshot` | D-1 is missing but D-2 exists | `daily.has_baseline is False` and D-2 items are not loaded |
| `test_sunday_loads_exact_current_and_previous_monday_sunday_ranges` | report date is 2026-08-23 | repository ranges are 2026-08-17..23 and 2026-08-10..16 |
| `test_different_page_scope_is_not_used_as_baseline` | previous pages=1, current pages=3 | `daily.has_baseline is False` |

- [ ] **Step 2: Write failing API contract tests**

```python
def test_daily_send_endpoint_forwards_date_and_keyword(monkeypatch) -> None:
    sender = Mock(return_value={"status": "sent", "snapshot_id": 17})
    client, app = daily_report_client(monkeypatch, sender)
    try:
        response = client.post(
            "/reports/daily/send?snapshot_date=2026-08-18&keyword=AI%20Agent",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sender.assert_called_once_with(
        ANY,
        snapshot_date=date(2026, 8, 18),
        keyword="AI Agent",
    )
```

Assert missing token returns 401 before DB access, no snapshot maps to 404, Telegram failure maps to 502, and status endpoint never exposes message text, Bot Token, Chat ID, or proxy configuration.

- [ ] **Step 3: Run the new service and API tests**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_daily_service.py tests/api/test_reports.py -q
```

Expected: FAIL because the daily service and endpoints do not exist.

- [ ] **Step 4: Implement report assembly before any external send**

The service must perform this order:

```python
header = get_snapshot(connection, snapshot_date=snapshot_date, search_keyword=keyword)
if header is None:
    raise DailySnapshotNotFound("daily snapshot not found")

delivery = get_delivery(connection, header.id)
if delivery.status == "completed":
    return {"status": "already_sent", "snapshot_id": header.id}

current_items = list_snapshot_items(connection, header.id)
previous_header = get_snapshot(
    connection,
    snapshot_date=snapshot_date - timedelta(days=1),
    search_keyword=keyword,
)
if previous_header is not None and (
    previous_header.search_keyword != header.search_keyword
    or previous_header.cities != header.cities
    or previous_header.pages_per_city != header.pages_per_city
    or previous_header.details_included != header.details_included
):
    previous_header = None
previous_items = () if previous_header is None else list_snapshot_items(connection, previous_header.id)
daily = compare_daily(current_items, previous_items if previous_header else None, cities=CITIES)
weekly = _load_weekly_comparison_if_sunday(connection, snapshot_date, keyword)
text = build_daily_brief(
    report_date=snapshot_date,
    keyword=keyword,
    city_count=header.city_count,
    pages_per_city=header.pages_per_city,
    daily=daily,
    weekly=weekly,
)
image = build_city_share_png(daily.city_metrics)
```

`_load_weekly_comparison_if_sunday` must apply the same four-field scope equality to every day in both weeks. A missing date or different scope returns no weekly comparison; it must never mix one-page legacy history with three-page V1.3 data.

Only after both `text` and `image` exist may the service send. Use the receipt values explicitly:

```python
text_receipt = text_sender(text)
record_text_sent(connection, header.id, text_receipt.message_id, text_receipt.attempts)
connection.commit()

photo_receipt = photo_sender(image)
record_photo_sent(connection, header.id, photo_receipt.message_id, photo_receipt.attempts)
connection.commit()
```

On `TelegramDeliveryError`, persist `exc.attempts` in the relevant failure transition, commit that transition, then re-raise a sanitized delivery error. After text success, a later service call skips text and starts with photo.

- [ ] **Step 5: Add daily API routes with the existing Bearer dependency**

Use explicit `date` parsing through FastAPI’s `datetime.date` type and default keyword `AI Agent`. Inject `get_daily_report_sender` just like the existing city sender, so tests can override it. Keep old city routes unchanged.

- [ ] **Step 6: Run service, API, and legacy report tests**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/reports/test_daily_service.py tests/reports/test_service.py tests/api/test_reports.py -q
<JOBFLOW_RUFF> check src/jobflow/reports/daily_service.py src/jobflow/api/reports.py tests/reports/test_daily_service.py tests/api/test_reports.py
```

Expected: new daily tests and all legacy query/AI report tests PASS.

- [ ] **Step 7: Approval-gated commit**

```powershell
git add src/jobflow/reports/daily_service.py src/jobflow/api/reports.py tests/reports/test_daily_service.py tests/api/test_reports.py
git commit -m "feat: deliver idempotent daily comparison reports"
```

### Task 10: Expand the Daily Script to Three Pages and Resume Existing Delivery

**Files:**

- Modify: `ops/daily_update.sh`
- Modify: `tests/ops/test_daily_update_script.py`

**Interfaces:**

- Sets: `KEYWORD="AI Agent"`, four fixed cities, and `PAGES=3`.
- Calls ETL with explicit date, keyword, city set, page count, and detail-mode metadata.
- Calls `POST /reports/daily/send` before capture to resume an existing snapshot and after ETL to deliver the new snapshot.
- Maintains the existing `flock`, login check, temp directory, and atomic final JSON replacement.

- [ ] **Step 1: Write failing script contract tests**

```python
def test_daily_update_uses_three_pages_without_details() -> None:
    text = read_script()

    assert 'KEYWORD="AI Agent"' in text
    assert 'PAGES=3' in text
    assert '--pages "$PAGES"' in text
    assert "--no-detail" in text
    assert text.count('"上海"') >= 1
    assert text.count('"北京"') >= 1
    assert text.count('"杭州"') >= 1
    assert text.count('"深圳"') >= 1


def test_daily_update_passes_snapshot_metadata_to_etl() -> None:
    text = read_script()

    assert "--snapshot-date" in text
    assert "--search-keyword" in text
    assert "--cities" in text
    assert "--pages-per-city" in text
    assert "--detail-mode" in text
    assert "/reports/daily/send" in text
    assert "/reports/cities/send?mode=query" not in text
```

Add assertions that merge code keeps one raw object per `job_id`, rejects a city with zero jobs, performs resume check before the first city loop, and does not print or source secrets on the host.

- [ ] **Step 2: Run script tests and verify old one-page behavior fails**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: FAIL because the script still contains `--pages 1` and the old city-query endpoint.

- [ ] **Step 3: Add fixed scope variables and identity deduplication**

At the script top use:

```bash
KEYWORD="AI Agent"
CITIES=("上海" "北京" "杭州" "深圳")
PAGES=3
SNAPSHOT_DATE="$(date +%F)"
```

Inside the Python merge block, require every city list to be non-empty and deduplicate by `job_id` while preserving first-seen order:

```python
all_jobs = []
seen_job_ids = set()
for city in cities:
    jobs = load_city_jobs(work_dir / f"{city}.json")
    if not jobs:
        raise ValueError(f"{city} 返回 0 条岗位，整批停止")
    for job in jobs:
        job_id = str(job.get("job_id", "")).strip()
        if not job_id:
            raise ValueError(f"{city} 存在缺少 job_id 的岗位")
        if job_id not in seen_job_ids:
            seen_job_ids.add(job_id)
            all_jobs.append(job)
```

- [ ] **Step 4: Pass explicit metadata into ETL**

```bash
docker compose run --rm etl \
    /data/raw/inbox/jobflow-four-cities.json \
    --snapshot-date "$SNAPSHOT_DATE" \
    --search-keyword "$KEYWORD" \
    --cities "$(IFS=,; echo "${CITIES[*]}")" \
    --pages-per-city "$PAGES" \
    --detail-mode no-detail
```

- [ ] **Step 5: Make the daily endpoint usable as a resume gate**

The existing in-container Python HTTP helper must distinguish:

```text
HTTP 404: no snapshot yet → return a dedicated shell code that allows capture
HTTP 200 + already_sent/sent: existing snapshot handled → exit the daily script successfully
HTTP 502/503/network error: abort; do not start a new capture over an existing uncertain state
```

Call this helper once before `cd "$SCRAPER_DIR"` and once after ETL. The first call may continue only on the dedicated no-snapshot result. The second call requires `sent` or `already_sent`.

- [ ] **Step 6: Run shell syntax, contract tests, and a safe mocked harness**

```powershell
bash -n ops/daily_update.sh
<JOBFLOW_PYTHON> -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: Bash syntax succeeds and all script contract tests PASS. Do not run a real BOSS capture or Telegram send in this local step.

- [ ] **Step 7: Approval-gated commit**

```powershell
git add ops/daily_update.sh tests/ops/test_daily_update_script.py
git commit -m "feat: expand and harden daily capture scope"
```

### Task 11: Audit Historical Batches and Backfill Only Explicitly Verified Scope

**Files:**

- Create: `src/jobflow/snapshot_backfill.py`
- Create: `tests/test_snapshot_backfill.py`

**Interfaces:**

- Produces CLI arguments demonstrated by `python -m jobflow.snapshot_backfill audit --start-date 2026-08-01 --end-date 2026-08-18`.
- Produces explicit backfill arguments demonstrated by `python -m jobflow.snapshot_backfill backfill --batch-id 42 --snapshot-date 2026-08-18 --search-keyword "AI Agent" --cities "上海,北京,杭州,深圳" --pages-per-city 1 --detail-mode no-detail --confirm-scope`.
- Audit is read-only. Backfill requires one explicit batch and `--confirm-scope`; it never sends Telegram messages.

- [ ] **Step 1: Write failing audit and safety-gate tests**

```python
def test_audit_lists_successful_batches_without_commit(monkeypatch, capsys) -> None:
    connection = audit_connection_fixture()
    monkeypatch.setattr(snapshot_backfill, "connect_postgres", lambda: connection)

    assert snapshot_backfill.main([
        "audit", "--start-date", "2026-08-01", "--end-date", "2026-08-18"
    ]) == 0
    assert "batch_id" in capsys.readouterr().out
    connection.commit.assert_not_called()


def test_backfill_requires_explicit_scope_confirmation(capsys) -> None:
    result = snapshot_backfill.main([
        "backfill",
        "--batch-id", "42",
        "--snapshot-date", "2026-08-18",
        "--search-keyword", "AI Agent",
        "--cities", "上海,北京,杭州,深圳",
        "--pages-per-city", "3",
        "--detail-mode", "no-detail",
    ])

    assert result == 2
    assert "--confirm-scope" in capsys.readouterr().err
```

Use this parametrized failure contract for unsafe candidates:

```python
@pytest.mark.parametrize(
    ("candidate", "message"),
    [
        ({"status": "failed", "row_count": 4, "raw_count": 4}, "succeeded"),
        ({"status": "succeeded", "row_count": 4, "raw_count": 3}, "row count"),
        ({"status": "succeeded", "row_count": 0, "raw_count": 0}, "non-empty"),
        ({"status": "succeeded", "row_count": 1, "raw_count": 1, "city": "广州"}, "declared city"),
    ],
)
def test_backfill_rejects_unsafe_candidate_without_commit(candidate, message, monkeypatch) -> None:
    connection = backfill_connection_fixture(candidate)
    monkeypatch.setattr(snapshot_backfill, "connect_postgres", lambda: connection)

    with pytest.raises(ValueError, match=message):
        snapshot_backfill.backfill_verified_batch(connection, verified_request_fixture())

    connection.commit.assert_not_called()
```

The verified success test must contain these assertions:

```python
snapshot_id = snapshot_backfill.backfill_verified_batch(connection, verified_request_fixture())

assert snapshot_id == 17
insert_snapshot.assert_called_once()
assert insert_snapshot.call_args.kwargs["metadata"].pages_per_city == 1
connection.commit.assert_called_once_with()
assert get_delivery(connection, 17).status == "pending"
assert "jobflow.channels.telegram" not in imported_during_call
```

- [ ] **Step 2: Run tests and confirm the CLI is missing**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/test_snapshot_backfill.py -q
```

Expected: FAIL because `jobflow.snapshot_backfill` does not exist.

- [ ] **Step 3: Implement a read-only audit query**

Audit query columns must be limited to non-secret evidence:

```sql
SELECT
    b.id,
    b.status,
    b.started_at::date,
    b.row_count,
    COUNT(r.id) AS raw_count,
    COUNT(DISTINCT r.payload ->> 'location') AS raw_location_count
FROM ops.batches AS b
LEFT JOIN raw.job_records AS r ON r.batch_id = b.id
WHERE b.started_at::date BETWEEN %s AND %s
GROUP BY b.id, b.status, b.started_at::date, b.row_count
ORDER BY b.started_at::date, b.id;
```

Print batch ID, date, status, declared row count, raw count, and location count. Do not print full payloads, cookies, URLs containing credentials, or environment values. Always rollback/close after audit.

- [ ] **Step 4: Implement explicit verified backfill**

Load the selected succeeded batch and map its raw payloads through the existing BOSS Adapter. Verify:

```text
batch status is succeeded
raw row count equals batch row_count
mapped job list is non-empty
every mapped city belongs to the declared city set
no duplicate (source, external_id)
no existing snapshot for the same date and keyword
--confirm-scope is present
```

Then call `insert_snapshot` in one transaction and commit. Do not send Telegram. A one-page legacy batch may be archived with `pages_per_city=1`, but Task 9 must refuse to use it as a baseline for a three-page snapshot.

- [ ] **Step 5: Run backfill tests and Ruff**

```powershell
<JOBFLOW_PYTHON> -m pytest tests/test_snapshot_backfill.py -q
<JOBFLOW_RUFF> check src/jobflow/snapshot_backfill.py tests/test_snapshot_backfill.py
```

Expected: audit is read-only, unsafe backfills fail closed, verified backfill is idempotent or reports the existing snapshot without duplication.

- [ ] **Step 6: Perform the Ubuntu audit without mutation**

After code is deployed but before any backfill:

```bash
cd <JOBFLOW_DIR>
docker compose exec -T api python -m jobflow.snapshot_backfill audit \
  --start-date 2026-08-01 \
  --end-date 2026-08-18
```

Expected: non-secret batch summary only. Record which dates are one-page legacy scope. Do not run `backfill` until each batch is manually verified against server logs.

- [ ] **Step 7: Approval-gated commit**

```powershell
git add src/jobflow/snapshot_backfill.py tests/test_snapshot_backfill.py
git commit -m "feat: audit and safely backfill snapshots"
```

### Task 12: Full Regression, Ubuntu Deployment, Real Telegram Acceptance, and Documentation

**Files:**

- Modify after evidence: `README.md`
- Modify after evidence: `docs/reference/architecture.md`
- Modify after evidence: `docs/project-handoff.md`
- Modify after evidence: `docs/guides/ubuntu-deployment.md`
- Update after completion: `<KNOWLEDGE_VAULT>` using its established daily-note and knowledge-card structure.

**Interfaces:**

- Produces: locally verified V1.3 candidate, then Ubuntu deployed candidate, then real Telegram acceptance evidence.
- Does not claim completion until database, systemd journal, and phone delivery agree.

- [ ] **Step 1: Run the complete local quality gate sequentially**

```powershell
<JOBFLOW_RUFF> check .
<JOBFLOW_PYTHON> -m pytest -q
```

Expected: Ruff exits 0 and the full test suite passes. Record the actual test count; do not copy an old count from documentation.

- [ ] **Step 2: Validate Compose configuration and build**

```powershell
docker compose config --quiet
docker compose build api
docker compose run --rm migrate
docker compose up -d api
docker compose ps
```

Expected: Compose config is valid, migration 006 applies, API health becomes healthy, and no secret value is printed.

- [ ] **Step 3: Inspect Git before any authorization request**

```powershell
git status --short --branch
git diff --stat
git diff --check
git log -5 --oneline
```

Expected: only intended V1.3 files plus pre-existing user documentation changes appear. `.superpowers/` remains untracked and must not be staged.

- [ ] **Step 4: Request explicit commit and push authorization**

Report the exact files, test count, branch, and diff summary. Commit and push only after the user explicitly authorizes them. Do not combine unrelated pre-existing docs unless the user includes them in the authorization.

- [ ] **Step 5: Deploy the authorized revision to Ubuntu**

```bash
ssh <SSH_USER>@<SERVER_IP>
cd <JOBFLOW_DIR>
git status --short --branch
git pull --ff-only origin main
docker compose run --rm migrate
docker compose build api
docker compose up -d api
docker compose ps
```

Expected: server worktree is understood before pull, migration succeeds, API is healthy, PostgreSQL data volume remains intact, and the exact deployed commit is recorded with `git rev-parse --short HEAD`.

- [ ] **Step 6: Run one real three-page manual acceptance only after explicit approval**

```bash
cd <JOBFLOW_DIR>
./ops/daily_update.sh
```

Expected: four cities each complete three-page list capture, one formal same-scope snapshot is stored, daily comparison correctly reports no same-scope baseline on the first V1.3 day, and the phone receives text followed by PNG.

- [ ] **Step 7: Verify database evidence without exposing secrets**

```bash
cd <JOBFLOW_DIR>
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT snapshot_date, search_keyword, city_count, cities, pages_per_city, details_included, status FROM core.job_snapshots ORDER BY snapshot_date DESC LIMIT 5;"'
```

The variables expand only inside the configured PostgreSQL container; do not echo `.env` values. Expected newest row: keyword `AI Agent`, four target cities, `pages_per_city=3`, `details_included=false`, `status=succeeded`.

- [ ] **Step 8: Verify delivery evidence and partial retry**

Query `ops.report_deliveries` for status and message IDs without printing Bot Token or Chat ID. In a controlled test, inject one image failure, verify text arrives once and status becomes `partial_failed`, restore networking, call `POST /reports/daily/send` again, and verify only the PNG is added and status becomes `completed`.

- [ ] **Step 9: Create one five-minute transient timer**

```bash
sudo systemd-run \
  --unit=jobflow-v13-smoke \
  --on-active=5m \
  /usr/bin/systemctl start jobflow-daily-update.service

systemctl status jobflow-v13-smoke.timer --no-pager
```

Expected: the transient timer is waiting. Five minutes later, check:

```bash
sudo journalctl -u jobflow-daily-update.service --since "15 minutes ago" --no-pager
systemctl status jobflow-daily-update.service --no-pager
```

Acceptance requires `status=0/SUCCESS`, a successful snapshot/delivery database row, and both messages visible on the phone. Stop the transient timer if it still exists; do not modify the formal 09:00 timer.

- [ ] **Step 10: Update public and private documentation from actual evidence**

Public README uses placeholders for user-specific values and documents:

```text
fresh clone and .env.example setup
Docker Compose startup
V1.3 migration and daily update entrypoints
three-page default scope and DIY variables/code locations
Telegram text plus PNG behavior
optional proxy requirement without personal subscription details
maintenance, logs, retry, and VNC login recovery
```

Private knowledge base records the actual server paths, systemd units, commands, expected results, comparison formulas, Matplotlib/PNG flow, Telegram multipart upload, message-id idempotency, migration, task lock, time lock, and same-scope comparison rule. Create or update only the 2026-08-18 daily note; do not pre-create a future date.

- [ ] **Step 11: Run documentation safety checks**

Search all changed Markdown for actual tokens, keys, subscriptions, passwords, webhooks, cookies, private keys, personal `.env` values, unclosed fences, and unresolved placeholders. Verify public examples use neutral placeholders and private notes contain no secret values.

- [ ] **Step 12: Approval-gated final documentation commit**

```powershell
git add README.md docs/reference/architecture.md docs/project-handoff.md docs/guides/ubuntu-deployment.md docs/archive/specs/2026-08-18-v1-3-daily-comparison-brief-design.md docs/archive/plans/2026-08-18-v1-3-daily-comparison-brief.md
git commit -m "docs: document JobFlow V1.3 operations"
```

Do not stage `.superpowers/`, real data, `.env`, or private Obsidian notes. Do not run the commit or push without explicit authorization.

## Final Acceptance Checklist

- [ ] Four cities × three pages × `AI Agent` × `--no-detail` is proven by server logs.
- [ ] Any city failure prevents formal snapshot creation and delivery.
- [ ] Snapshot identity, scope, and batch linkage are queryable.
- [ ] One-page legacy history is never compared with three-page V1.3 history.
- [ ] Daily comparison uses only the previous natural day with identical scope.
- [ ] Sunday weekly comparison uses two complete same-scope Monday-Sunday periods.
- [ ] Salary median excludes daily/hourly jobs; skills count once per job.
- [ ] Approved management-dashboard text stays under 4096 characters.
- [ ] City values sum to total and match the PNG.
- [ ] Telegram text arrives before PNG.
- [ ] Photo retry does not duplicate text.
- [ ] Local full suite, Compose build, migration, Ubuntu manual run, and five-minute timer all pass.
- [ ] README, handoff, deployment guide, architecture, and knowledge base reflect only verified status.
- [ ] No secret or personal subscription value appears in Git or logs.
