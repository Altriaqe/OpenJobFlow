from pathlib import Path
import pytest

from jobflow.models.job import JobRecord
from jobflow.adapters.boss import SnapshotError


def test_run_boss_snapshot_orchestrates_etl(monkeypatch):
    """测试 run_boss_snapshot() 函数是否正确调用 ETL 流程"""
    from jobflow.workers import etl as etl_worker

    # 测试假数据
    snapshot_path = Path("snapshot.json")
    raw_jobs = [{"job_id": "job-001"}]
    jobs = [
        JobRecord(
            source="boss_zhipin",
            external_id="job-001",
            title="Python开发工程师",
            company="示例公司",
            city="兰州",
            detail_url="https://example.com/jobs/001",
        )
    ]

    calls = {}

    def fake_load_boss_jobs(path):
        calls["load_path"] = path
        return raw_jobs

    def fake_map_boss_jobs(received_raw_jobs):
        calls["map_input"] = received_raw_jobs
        return jobs

    def fake_run_job_batch(received_raw_jobs, received_jobs, snapshot_metadata=None):
        calls["batch_raw_input"] = received_raw_jobs
        calls["batch_job_input"] = received_jobs
        calls["snapshot_metadata"] = snapshot_metadata

    monkeypatch.setattr(etl_worker, "load_boss_jobs", fake_load_boss_jobs)
    monkeypatch.setattr(etl_worker, "map_boss_jobs", fake_map_boss_jobs)
    monkeypatch.setattr(etl_worker, "run_job_batch", fake_run_job_batch)

    # 调用被测试函数
    etl_worker.run_boss_snapshot(snapshot_path)

    assert calls["load_path"] == snapshot_path
    assert calls["map_input"] == raw_jobs
    assert calls["batch_raw_input"] == raw_jobs
    assert calls["batch_job_input"] == jobs
    assert calls["snapshot_metadata"] is None


def test_run_boss_snapshot_stops_when_snapshot_load_fails(monkeypatch):
    """测试 run_boss_snapshot() 函数在加载快照失败时是否停止执行"""
    from jobflow.workers import etl as etl_worker

    snapshot_path = Path("missing.json")

    def failing_load(path):
        raise SnapshotError("快照读取失败：{path}")

    def unexpected_map(raw_jobs):
        pytest.fail("读取失败后不应继续映射")

    def unexpected_batch(raw_jobs, jobs):
        pytest.fail("读取失败后不应继续写入")

    monkeypatch.setattr(etl_worker, "load_boss_jobs", failing_load)
    monkeypatch.setattr(etl_worker, "map_boss_jobs", unexpected_map)
    monkeypatch.setattr(etl_worker, "run_job_batch", unexpected_batch)

    with pytest.raises(SnapshotError, match="快照读取失败"):
        etl_worker.run_boss_snapshot(snapshot_path)


def test_run_boss_snapshot_propagates_database_error(monkeypatch):
    from jobflow.workers import etl as etl_worker

    snapshot_path = Path("snapshot.json")

    normalized_jobs = [
        JobRecord(
            source="boss_zhipin",
            external_id="job-001",
            title="Python开发工程师",
            company="示例公司",
            city="兰州",
            detail_url="https://example.com/jobs/001",
        )
    ]

    def fake_map_boss_jobs(raw_jobs):
        return normalized_jobs

    monkeypatch.setattr(etl_worker, "load_boss_jobs", lambda path: [{"job_id": "job-001"}])
    monkeypatch.setattr(etl_worker, "map_boss_jobs", fake_map_boss_jobs)

    def failing_run_job_batch(raw_jobs, jobs, snapshot_metadata=None):
        raise RuntimeError("数据库写入失败")

    monkeypatch.setattr(etl_worker, "run_job_batch", failing_run_job_batch)

    with pytest.raises(RuntimeError, match="数据库写入失败"):
        etl_worker.run_boss_snapshot(snapshot_path)


def test_run_boss_snapshot_skips_database_when_no_jobs(monkeypatch):
    """测试 run_boss_snapshot() 函数在没有岗位数据的情况下是否跳过数据库写入"""
    from jobflow.workers import etl as etl_worker

    monkeypatch.setattr(etl_worker, "load_boss_jobs", lambda path: [])
    monkeypatch.setattr(etl_worker, "map_boss_jobs", lambda raw_jobs: [])

    def unexpected_batch(raw_jobs, jobs):
        pytest.fail("空岗位不应进入数据库写入层")

    monkeypatch.setattr(etl_worker, "run_job_batch", unexpected_batch)

    etl_worker.run_boss_snapshot(Path("empty.json"))
