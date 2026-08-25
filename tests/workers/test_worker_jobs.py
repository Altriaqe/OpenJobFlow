from datetime import date

import pytest

from jobflow.models.job import JobRecord
from jobflow.models.snapshot import SnapshotMetadata


def test_run_job_batch_commits_and_closes_on_success(monkeypatch):
    """测试 run_job_batch 在成功时是否提交事务并关闭连接"""
    from jobflow.workers import jobs as worker_jobs

    class FakeConnection:
        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def commit(self):
            # 模拟提交事务
            self.committed = True

        def rollback(self):
            # 模拟回滚事务
            self.rolled_back = True

        def close(self):
            # 模拟关闭连接
            self.closed = True

    fake_connection = FakeConnection()

    received = {}

    def fake_insert_jobs(connection, jobs):
        received["connection"] = connection
        received["jobs"] = jobs

    monkeypatch.setattr(
        worker_jobs, "connect_postgres", lambda: fake_connection
    )  # Worker 调用 connect_postgres() → 实际得到 fake_connection

    monkeypatch.setattr(worker_jobs, "insert_jobs", fake_insert_jobs)

    monkeypatch.setattr(
        worker_jobs,
        "start_batch",
        lambda connection, source: 101,
    )

    monkeypatch.setattr(
        worker_jobs,
        "finish_batch",
        lambda connection, batch_id, row_count: None,
    )

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

    jobs_to_insert = [first_job, second_job]
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

    worker_jobs.run_job_batch(raw_jobs, jobs_to_insert)

    assert (
        received["connection"] is fake_connection
    )  # Worker 调用 connect_postgres() → 实际得到 fake_connection
    assert received["jobs"] == jobs_to_insert  # Worker 调用 insert_jobs() → 实际传入 jobs_to_insert
    assert fake_connection.committed  # Worker 调用 commit() → 实际提交事务
    assert not fake_connection.rolled_back  # Worker 没有调用 rollback() → 实际没有回滚事务
    assert fake_connection.closed  # Worker 调用 close() → 实际关闭连接


def test_run_job_batch_rolls_back_and_closes_on_failure(monkeypatch):
    """测试在失败的时候执行回滚并关闭连接"""
    from jobflow.workers import jobs as worker_jobs

    class FakeConnection:
        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def commit(self):
            # 模拟提交事务
            self.committed = True

        def rollback(self):
            # 模拟回滚事务
            self.rolled_back = True

        def close(self):
            # 模拟关闭连接
            self.closed = True

    def failing_insert_jobs(connection, jobs):
        raise RuntimeError("insert failed")

    fake_connection = FakeConnection()

    monkeypatch.setattr(
        worker_jobs, "connect_postgres", lambda: fake_connection
    )  # Worker 调用 connect_postgres() → 实际得到 fake_connection
    monkeypatch.setattr(worker_jobs, "insert_jobs", failing_insert_jobs)

    with pytest.raises(RuntimeError, match="insert failed"):
        worker_jobs.run_job_batch([], [])  # 传入空列表以触发失败

    assert fake_connection.committed is False  # Worker 没有调用 commit() → 实际没有提交事务
    assert fake_connection.rolled_back is True  # Worker 调用 rollback() → 实际回滚事务
    assert fake_connection.closed is True  # Worker 调用 close() → 实际关闭连接


def test_run_job_batch_records_successful_batch(monkeypatch):
    """测试成功批次的状态记录和事务顺序。"""
    from jobflow.workers import jobs as worker_jobs

    events = []

    class FakeConnection:
        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    fake_connection = FakeConnection()

    job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/001",
    )
    raw_jobs = [
        {
            "job_id": "job-001",
            "title": "Python开发工程师",
            "boss_name": "示例公司",
            "location": "兰州",
            "job_link": "https://example.com/jobs/001",
        }
    ]

    def fake_start_batch(connection, source):
        assert connection is fake_connection
        events.append(("start_batch", source))
        return 101

    def fake_insert_jobs(connection, jobs):
        assert connection is fake_connection
        assert jobs == [job]
        events.append("insert_jobs")

    def fake_insert_raw_jobs(connection, batch_id, raw_jobs, jobs):
        assert connection is fake_connection
        assert batch_id == 101
        assert raw_jobs[0]["job_id"] == "job-001"
        assert jobs == [job]
        events.append("insert_raw_jobs")

    def fake_finish_batch(connection, batch_id, row_count):
        assert connection is fake_connection
        events.append(("finish_batch", batch_id, row_count))

    monkeypatch.setattr(
        worker_jobs,
        "connect_postgres",
        lambda: fake_connection,
    )
    monkeypatch.setattr(
        worker_jobs,
        "start_batch",
        fake_start_batch,
        raising=False,
    )
    monkeypatch.setattr(
        worker_jobs,
        "insert_jobs",
        fake_insert_jobs,
    )
    monkeypatch.setattr(
        worker_jobs,
        "insert_raw_jobs",
        fake_insert_raw_jobs,
        raising=False,
    )
    monkeypatch.setattr(
        worker_jobs,
        "finish_batch",
        fake_finish_batch,
        raising=False,
    )

    worker_jobs.run_job_batch(raw_jobs, [job])

    assert events == [
        ("start_batch", "boss_zhipin"),
        "commit",
        "insert_raw_jobs",
        "insert_jobs",
        ("finish_batch", 101, 1),
        "commit",
        "close",
    ]


def test_run_job_batch_records_failed_batch(monkeypatch):
    """测试岗位写入失败时记录失败批次，并继续抛出原异常。"""
    from jobflow.workers import jobs as worker_jobs

    events = []

    class FakeConnection:
        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    fake_connection = FakeConnection()

    job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="Python开发工程师",
        company="示例公司",
        city="兰州",
        detail_url="https://example.com/jobs/001",
    )
    raw_jobs = [
        {
            "job_id": "job-001",
            "title": "Python开发工程师",
            "boss_name": "示例公司",
            "location": "兰州",
            "job_link": "https://example.com/jobs/001",
        }
    ]

    def fake_start_batch(connection, source):
        assert connection is fake_connection
        events.append(("start_batch", source))
        return 101

    def failing_insert_jobs(connection, jobs):
        assert connection is fake_connection
        assert jobs == [job]
        events.append("insert_jobs")
        raise RuntimeError("insert failed")

    def fake_insert_raw_jobs(connection, batch_id, raw_jobs, jobs):
        assert connection is fake_connection
        assert batch_id == 101
        assert raw_jobs[0]["job_id"] == "job-001"
        assert jobs == [job]
        events.append("insert_raw_jobs")

    def fake_fail_batch(connection, batch_id, error_message):
        assert connection is fake_connection
        events.append(("fail_batch", batch_id, error_message))

    monkeypatch.setattr(
        worker_jobs,
        "connect_postgres",
        lambda: fake_connection,
    )
    monkeypatch.setattr(
        worker_jobs,
        "start_batch",
        fake_start_batch,
    )
    monkeypatch.setattr(
        worker_jobs,
        "insert_jobs",
        failing_insert_jobs,
    )
    monkeypatch.setattr(
        worker_jobs,
        "insert_raw_jobs",
        fake_insert_raw_jobs,
        raising=False,
    )
    monkeypatch.setattr(
        worker_jobs,
        "fail_batch",
        fake_fail_batch,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="insert failed"):
        worker_jobs.run_job_batch(raw_jobs, [job])

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


def test_run_job_batch_writes_snapshot_before_finishing_batch(monkeypatch):
    from jobflow.workers import jobs as worker_jobs

    events = []

    class FakeConnection:
        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    job = JobRecord(
        source="boss_zhipin",
        external_id="job-001",
        title="AI Agent 工程师",
        company="示例公司",
        city="上海",
        detail_url="https://example.com/job-001",
    )
    metadata = SnapshotMetadata(
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )

    monkeypatch.setattr(worker_jobs, "connect_postgres", FakeConnection)
    monkeypatch.setattr(worker_jobs, "start_batch", lambda connection, source: 42)
    monkeypatch.setattr(
        worker_jobs,
        "insert_raw_jobs",
        lambda connection, batch_id, raw_jobs, jobs: events.append("raw"),
    )
    monkeypatch.setattr(
        worker_jobs,
        "insert_jobs",
        lambda connection, jobs: events.append("core"),
    )
    monkeypatch.setattr(
        worker_jobs,
        "insert_snapshot",
        lambda connection, batch_id, metadata, jobs: events.append("snapshot"),
    )
    monkeypatch.setattr(
        worker_jobs,
        "finish_batch",
        lambda connection, batch_id, row_count: events.append("finish"),
    )

    batch_id = worker_jobs.run_job_batch(
        [{"job_id": "job-001"}],
        [job],
        snapshot_metadata=metadata,
    )

    assert batch_id == 42
    assert events == [
        "commit",
        "raw",
        "core",
        "snapshot",
        "finish",
        "commit",
        "close",
    ]
