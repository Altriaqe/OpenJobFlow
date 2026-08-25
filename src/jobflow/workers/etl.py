from pathlib import Path

from jobflow.adapters.boss import load_boss_jobs, map_boss_jobs
from jobflow.models.snapshot import SnapshotMetadata
from jobflow.workers.jobs import run_job_batch


def run_boss_snapshot(
    path: Path,
    metadata: SnapshotMetadata | None = None,
) -> int | None:
    """运行 Boss 直聘岗位快照 ETL 流程"""
    raw_jobs = load_boss_jobs(path)
    jobs = map_boss_jobs(raw_jobs)
    if not jobs:
        return None  # 如果没有岗位数据，则不执行批量插入，提前返回
    return run_job_batch(raw_jobs, jobs, snapshot_metadata=metadata)
