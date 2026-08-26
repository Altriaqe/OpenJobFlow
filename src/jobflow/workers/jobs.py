"""岗位批次事务编排：统一提交成功结果，失败时回滚并记录批次错误。"""

from jobflow.db.batches import fail_batch, finish_batch, start_batch
from jobflow.db.connection import connect_postgres
from jobflow.db.jobs import insert_jobs
from jobflow.db.raw_jobs import insert_raw_jobs
from jobflow.db.snapshots import insert_snapshot
from jobflow.models.job import JobRecord
from jobflow.models.snapshot import SnapshotMetadata


def run_job_batch(
    raw_jobs: list[dict[str, str]],
    jobs: list[JobRecord],
    snapshot_metadata: SnapshotMetadata | None = None,
) -> int | None:
    """在一个数据库连接中完成 raw/core/snapshot 写入并管理批次事务。"""
    connection = connect_postgres()
    batch_id = None

    try:
        # 先建立批次，再写 raw/core/snapshot；所有成功写入最终由一次 commit 固化。
        if jobs:
            batch_id = start_batch(connection, jobs[0].source)
            connection.commit()  # 提交事务

        if batch_id is not None:
            insert_raw_jobs(
                connection,
                batch_id=batch_id,
                raw_jobs=raw_jobs,
                jobs=jobs,
            )

        insert_jobs(connection, jobs)

        if batch_id is not None:
            if snapshot_metadata is not None:
                insert_snapshot(
                    connection,
                    batch_id=batch_id,
                    metadata=snapshot_metadata,
                    jobs=jobs,
                )
            finish_batch(connection, batch_id=batch_id, row_count=len(jobs))

        connection.commit()  # 提交事务
        return batch_id
    except Exception as exc:
        connection.rollback()  # 回滚事务

        if batch_id is not None:
            fail_batch(connection, batch_id=batch_id, error_message=str(exc))
            connection.commit()  # 提交事务

        raise
    finally:
        connection.close()  # 关闭连接
