from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

import psycopg
import pytest

from jobflow.db.batches import fail_batch, finish_batch, start_batch
from jobflow.db.connection import connect_postgres
from jobflow.db.jobs import insert_job
from jobflow.db.raw_jobs import insert_raw_job
from jobflow.db.snapshots import insert_snapshot
from jobflow.models.job import JobRecord
from jobflow.models.snapshot import SnapshotMetadata
from jobflow.workers.jobs import run_job_batch
from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app


@pytest.fixture()  # 用于提供一个 PostgreSQL 数据库连接的 pytest fixture
def postgres_connection():
    """提供一个 PostgreSQL 数据库连接的 pytest fixture"""
    connection = connect_postgres()

    try:
        yield connection
    finally:
        connection.rollback()  # 回滚任何未提交的事务
        connection.close()  # 确保连接被关闭


def test_postgres_connection_works(postgres_connection):
    """测试 PostgreSQL 数据库连接是否正常工作"""
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1")

    result = cursor.fetchone()

    assert result == (1,)


def test_insert_job_upserts_in_real_postgres(postgres_connection):
    """测试 insert_job() 函数在真实 PostgreSQL 数据库中是否正确执行插入和更新操作"""
    first_job = JobRecord(
        source="integration_test",
        external_id="integration-test-job-001",
        title="Python 开发工程师",
        company="集成测试公司",
        city="兰州",
        detail_url="https://example.com/integration-001",
    )

    second_job = JobRecord(
        source="integration_test",
        external_id="integration-test-job-001",
        title="高级 Python 开发工程师",
        company="集成测试公司",
        city="兰州",
        detail_url="https://example.com/integration-001",
    )

    insert_job(postgres_connection, first_job)
    insert_job(postgres_connection, second_job)

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*), MAX(title)
        FROM core.jobs
        WHERE source = %s AND external_id = %s
        """,
        (second_job.source, second_job.external_id),
    )

    count, title = cursor.fetchone()

    assert count == 1
    assert title == "高级 Python 开发工程师"


def test_insert_job_can_be_rolled_back(postgres_connection):
    """测试 insert_job() 函数的事务是否可以回滚"""
    job = JobRecord(
        source="integration_test",
        external_id="integration-test-job-rollback",
        title="Python 开发工程师",
        company="集成测试公司",
        city="兰州",
        detail_url="https://example.com/integration-rollback",
    )

    insert_job(postgres_connection, job)

    # 回滚事务
    postgres_connection.rollback()

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM core.jobs
        WHERE source = %s AND external_id = %s
        """,
        (job.source, job.external_id),
    )

    count = cursor.fetchone()[0]

    assert count == 0


def test_batch_success_lifecycle_in_real_postgres(postgres_connection):
    """测试批次的成功生命周期在真实 PostgreSQL 数据库中是否正确执行"""
    batch_id = start_batch(postgres_connection, "integration_test")

    finish_batch(postgres_connection, batch_id=batch_id, row_count=30)

    curor = postgres_connection.cursor()
    curor.execute(
        """
        SELECT status, row_count, finished_at
        FROM ops.batches
        WHERE id = %s
        """,
        (batch_id,),
    )

    status, row_count, finished_at = curor.fetchone()

    assert status == "succeeded"
    assert row_count == 30
    assert finished_at is not None


def test_batch_failure_lifecycle_in_real_postgres(postgres_connection):
    """测试批次的失败生命周期在真实 PostgreSQL 数据库中是否正确执行"""
    batch_id = start_batch(postgres_connection, source="integration_test")

    fail_batch(postgres_connection, batch_id=batch_id, error_message="集成测试失败")

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT status, error_message, finished_at
        FROM ops.batches
        WHERE id = %s
        """,
        (batch_id,),
    )

    status, error_message, finished_at = cursor.fetchone()

    assert status == "failed"
    assert error_message == "集成测试失败"
    assert finished_at is not None


def test_raw_job_rejects_missing_batch_in_real_postgres(postgres_connection):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert_raw_job(
            postgres_connection,
            batch_id=9_999_999_999,
            source="integration_test",
            external_id="missing-batch-job",
            payload={"job_id": "missing-batch-job"},
        )


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


def test_city_job_counts_view_updates_without_refresh(postgres_connection):
    """验证普通 View 会随 core.jobs 数据变化自动返回最新统计"""
    city = f"mart-test-{uuid4()}"

    for index in (1, 2):
        job = JobRecord(
            source="integration_mart",
            external_id=f"{city}-{index}",
            title=f"Test Job {index}",
            company="Test Company",
            city=city,
            detail_url=f"https://example.com/{city}-{index}",
        )
        insert_job(postgres_connection, job)

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT job_count
        FROM mart.city_job_counts
        WHERE city = %s
        """,
        (city,),
    )

    assert cursor.fetchone() == (2,)

    third_job = JobRecord(
        source="integration_mart",
        external_id=f"{city}-3",
        title="Test Job 3",
        company="Test Company",
        city=city,
        detail_url=f"https://example.com/{city}-3",
    )
    insert_job(postgres_connection, third_job)

    cursor.execute(
        """
        SELECT job_count
        FROM mart.city_job_counts
        WHERE city = %s
        """,
        (city,),
    )

    assert cursor.fetchone() == (3,)


def test_city_analytics_api_reads_real_postgres(postgres_connection):
    """验证 /analytics/cities API 能够从真实 PostgreSQL 数据库中读取数据"""
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
    assert {"city": city, "job_count": 2} in response.json()


def test_salary_and_skill_views_use_normalized_core_fields(postgres_connection):
    city = f"salary-mart-{uuid4()}"
    skill = f"skill-{uuid4()}"
    source = f"integration_salary_skill_{uuid4()}"

    jobs = [
        JobRecord(
            source=source,
            external_id="monthly-1",
            title="Monthly Job 1",
            company="Test Company",
            city=city,
            detail_url="https://example.com/monthly-1",
            salary_text="10-20K",
            salary_min=10,
            salary_max=20,
            salary_unit="K_PER_MONTH",
            skills=[skill, "Python"],
        ),
        JobRecord(
            source=source,
            external_id="monthly-2",
            title="Monthly Job 2",
            company="Test Company",
            city=city,
            detail_url="https://example.com/monthly-2",
            salary_text="20-30K·14薪",
            salary_min=20,
            salary_max=30,
            salary_unit="K_PER_MONTH",
            salary_months=14,
            skills=[skill],
        ),
        JobRecord(
            source=source,
            external_id="monthly-cny",
            title="Monthly CNY Job",
            company="Test Company",
            city=city,
            detail_url="https://example.com/monthly-cny",
            salary_text="3500-5500元/月",
            salary_min=3500,
            salary_max=5500,
            salary_unit="CNY_PER_MONTH",
            skills=[],
        ),
        JobRecord(
            source=source,
            external_id="daily-1",
            title="Daily Job",
            company="Test Company",
            city=city,
            detail_url="https://example.com/daily-1",
            salary_text="200-300元/天",
            salary_min=200,
            salary_max=300,
            salary_unit="CNY_PER_DAY",
            skills=[],
        ),
    ]

    for job in jobs:
        insert_job(postgres_connection, job)

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT job_count, avg_salary_min, avg_salary_max, avg_salary_mid
        FROM mart.city_salary_stats
        WHERE city = %s
        """,
        (city,),
    )
    salary_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT job_count
        FROM mart.skill_job_counts
        WHERE skill = %s
        """,
        (skill,),
    )
    skill_row = cursor.fetchone()

    assert salary_row == (
        3,
        Decimal("11.17"),
        Decimal("18.50"),
        Decimal("14.83"),
    )
    assert skill_row == (2,)


def test_snapshot_table_accepts_cny_monthly_salary(postgres_connection) -> None:
    unique = str(uuid4())
    batch_id = start_batch(postgres_connection, f"integration_snapshot_{unique}")
    job = JobRecord(
        source=f"integration_snapshot_{unique}",
        external_id="cny-monthly",
        title="CNY Monthly Job",
        company="Test Company",
        city="上海",
        detail_url=f"https://example.com/{unique}",
        salary_text="3500-5500元/月",
        salary_min=3500,
        salary_max=5500,
        salary_unit="CNY_PER_MONTH",
        skills=[],
    )

    snapshot_id = insert_snapshot(
        postgres_connection,
        batch_id=batch_id,
        metadata=SnapshotMetadata(
            snapshot_date=date(2026, 8, 23),
            search_keyword=f"integration-{unique}",
            cities=("上海",),
            pages_per_city=1,
            details_included=False,
        ),
        jobs=[job],
    )

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT salary_min, salary_max, salary_unit
        FROM core.job_snapshot_items
        WHERE snapshot_id = %s
        """,
        (snapshot_id,),
    )

    assert cursor.fetchone() == (3500, 5500, "CNY_PER_MONTH")


def test_core_jobs_rejects_salary_months_for_cny_monthly(postgres_connection) -> None:
    unique = str(uuid4())
    job = JobRecord(
        source=f"integration_invalid_months_{unique}",
        external_id="cny-monthly-with-months",
        title="Invalid CNY Monthly Job",
        company="Test Company",
        city="上海",
        detail_url=f"https://example.com/{unique}",
        salary_text="3500-5500元/月",
        salary_min=3500,
        salary_max=5500,
        salary_unit="CNY_PER_MONTH",
        salary_months=14,
        skills=[],
    )

    with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
        insert_job(postgres_connection, job)

    assert exc_info.value.diag.constraint_name == "jobs_salary_values_check"


def test_snapshot_table_rejects_salary_months_for_cny_monthly(postgres_connection) -> None:
    unique = str(uuid4())
    batch_id = start_batch(postgres_connection, f"integration_invalid_snapshot_{unique}")
    job = JobRecord(
        source=f"integration_invalid_snapshot_{unique}",
        external_id="cny-monthly-with-months",
        title="Invalid CNY Monthly Snapshot Job",
        company="Test Company",
        city="上海",
        detail_url=f"https://example.com/{unique}",
        salary_text="3500-5500元/月",
        salary_min=3500,
        salary_max=5500,
        salary_unit="CNY_PER_MONTH",
        salary_months=14,
        skills=[],
    )

    with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
        insert_snapshot(
            postgres_connection,
            batch_id=batch_id,
            metadata=SnapshotMetadata(
                snapshot_date=date(2026, 8, 23),
                search_keyword=f"integration-invalid-{unique}",
                cities=("上海",),
                pages_per_city=1,
                details_included=False,
            ),
            jobs=[job],
        )

    assert exc_info.value.diag.constraint_name == "job_snapshot_items_salary_values_check"


def test_core_and_snapshot_tables_keep_negotiable_salary(postgres_connection) -> None:
    unique = str(uuid4())
    source = f"integration_negotiable_{unique}"
    job = JobRecord(
        source=source,
        external_id="negotiable",
        title="Negotiable Salary Job",
        company="Test Company",
        city="上海",
        detail_url=f"https://example.com/{unique}",
        salary_text="面议",
        salary_min=None,
        salary_max=None,
        salary_unit=None,
        salary_months=None,
        skills=[],
    )

    insert_job(postgres_connection, job)
    batch_id = start_batch(postgres_connection, f"integration_negotiable_{unique}")
    snapshot_id = insert_snapshot(
        postgres_connection,
        batch_id=batch_id,
        metadata=SnapshotMetadata(
            snapshot_date=date(2026, 8, 23),
            search_keyword=f"integration-negotiable-{unique}",
            cities=("上海",),
            pages_per_city=1,
            details_included=False,
        ),
        jobs=[job],
    )

    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        SELECT salary_text, salary_min, salary_max, salary_unit, salary_months
        FROM core.jobs
        WHERE source = %s AND external_id = %s
        """,
        (source, job.external_id),
    )
    core_salary = cursor.fetchone()
    cursor.execute(
        """
        SELECT salary_text, salary_min, salary_max, salary_unit, salary_months
        FROM core.job_snapshot_items
        WHERE snapshot_id = %s
        """,
        (snapshot_id,),
    )
    snapshot_salary = cursor.fetchone()

    assert core_salary == ("面议", None, None, None, None)
    assert snapshot_salary == ("面议", None, None, None, None)


def test_salary_and_skill_analytics_apis_read_real_postgres(postgres_connection):
    city = f"api-salary-{uuid4()}"
    skill = f"api-skill-{uuid4()}"
    source = f"integration_api_salary_skill_{uuid4()}"

    insert_job(
        postgres_connection,
        JobRecord(
            source=source,
            external_id="job-1",
            title="API Salary Job",
            company="API Company",
            city=city,
            detail_url="https://example.com/api-salary-job",
            salary_text="12-18K",
            salary_min=12,
            salary_max=18,
            salary_unit="K_PER_MONTH",
            skills=[skill],
        ),
    )

    app = create_app()
    app.dependency_overrides[get_connection] = lambda: postgres_connection
    client = TestClient(app)
    try:
        salary_response = client.get("/analytics/salaries/cities?limit=100")
        skill_response = client.get("/analytics/skills?limit=100")
    finally:
        app.dependency_overrides.clear()

    assert salary_response.status_code == 200
    assert any(
        row
        == {
            "city": city,
            "job_count": 1,
            "avg_salary_min": 12.0,
            "avg_salary_max": 18.0,
            "avg_salary_mid": 15.0,
        }
        for row in salary_response.json()
    )
    assert skill_response.status_code == 200
    assert {"skill": skill, "job_count": 1} in skill_response.json()
