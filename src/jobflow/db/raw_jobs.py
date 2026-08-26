"""raw 层写入：保存原始岗位载荷，支持审计和后续重新处理。"""

from psycopg.types.json import Jsonb

from jobflow.models.job import JobRecord


def insert_raw_job(
    connection,
    batch_id: int,
    source: str,
    external_id: str,
    payload: dict[str, str],
) -> None:
    """把单条原始岗位和批次关联后写入 raw 表；不在此处提交事务。"""
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
    """按标准化岗位顺序批量保存原始载荷，并校验两侧长度一致。"""
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
