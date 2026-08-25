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
