from jobflow.models.job import JobRecord
from jobflow.db.jobs import insert_job


class FakeCursor:
    # 模拟数据库游标，用于测试 insert_job 函数
    def __init__(self):
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))


class FakeConnection:
    # 模拟数据库连接，用于测试 insert_job 函数
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self):
        return self.fake_cursor


def test_insert_job_executes_idempotent_sql():
    """测试插入岗位数据时，SQL语句是否具有幂等性"""
    connection = FakeConnection()
    job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/001",
        salary_text="15-25K·14薪",
        salary_min=15,
        salary_max=25,
        salary_unit="K_PER_MONTH",
        salary_months=14,
        skills=["Python", "SQL"],
    )

    insert_job(connection, job)

    assert len(connection.fake_cursor.executed) == 1

    sql, params = connection.fake_cursor.executed[0]  # 序列解包

    assert "INSERT INTO core.jobs" in sql
    assert "ON CONFLICT (source, external_id)" in sql
    assert params == (
        "boss_zhipin",
        "job-001",
        "Python开发工程师",
        "示例公司",
        "兰州",
        "https://example.com/jobs/001",
        "15-25K·14薪",
        15,
        25,
        "K_PER_MONTH",
        14,
        ["Python", "SQL"],
    )


def test_insert_job_updates_last_seen_at_on_conflict():
    """测试在冲突时，last_seen_at 字段是否被更新"""
    connection = FakeConnection()
    job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/001",
    )

    insert_job(connection, job)

    sql, params = connection.fake_cursor.executed[0]

    assert "last_seen_at = CURRENT_TIMESTAMP" in sql
    assert "first_seen_at =" not in sql


def test_insert_job_updates_updated_at_only_when_business_fields_change():
    """测试仅在业务字段发生变化时更新 updated_at 字段"""
    connection = FakeConnection()
    job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/001",
    )

    insert_job(connection, job)

    sql, _ = connection.fake_cursor.executed[0]

    assert "updated_at = CASE" in sql
    assert "core.jobs.salary_text IS DISTINCT FROM EXCLUDED.salary_text" in sql
    assert "core.jobs.skills IS DISTINCT FROM EXCLUDED.skills" in sql


def test_insert_jobs_writes_jobs_in_input_order():
    """测试批量插入岗位数据时，是否按照输入顺序写入数据库"""
    from jobflow.db.jobs import insert_jobs

    connection = FakeConnection()
    first_job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/001",
    )
    second_job = JobRecord(
        source="boss_zhipin",
        external_id="job-002",
        title="Java开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/002",
    )

    jobs = [first_job, second_job]

    insert_jobs(connection, jobs)

    executed = connection.fake_cursor.executed

    assert len(executed) == 2
    assert executed[0][1][1] == "job-001"
    assert executed[1][1][1] == "job-002"
