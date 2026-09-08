"""运营看板的统一只读快照。"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection
from jobflow.db.operations import list_recent_checks, list_recent_runs
from jobflow.operations.models import load_stage_definitions
from jobflow.operations.stages import build_stage_snapshot, stage_evidence

router = APIRouter(prefix="/dashboard")


@router.get("/summary")
def get_dashboard_summary(connection=Depends(get_connection)):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT city) FROM core.jobs")
        job_count, city_count = cursor.fetchone()
        cursor.execute(
            "SELECT row_count, finished_at, status FROM ops.batches ORDER BY id DESC LIMIT 1"
        )
        batch = cursor.fetchone()
        cursor.execute(
            """SELECT channel, status, updated_at
               FROM ops.report_channel_deliveries
               ORDER BY updated_at DESC"""
        )
        channel_rows = cursor.fetchall()
        checks = list_recent_checks(connection)
        runs = list_recent_runs(connection, limit=10)
        definitions = load_stage_definitions(Path.cwd() / "config" / "platform_stages.yaml")
        stages = build_stage_snapshot(definitions, stage_evidence(checks))
        alerts = [
            {"level": "告警", "title": f"{item.name} 检查失败", "detail": item.summary}
            for item in checks
            if item.status == "failed"
        ]
        return {
            "metrics": {
                "job_count": job_count,
                "city_count": city_count,
                "batch_row_count": None if batch is None else batch[0],
                "batch_status": None if batch is None else batch[2],
            },
            "batch_finished_at": None if batch is None else batch[1],
            "stages": [
                {"id": item.definition.id, "name": item.definition.name, "state": item.state.value}
                for item in stages
            ],
            "checks": [
                {"name": item.name, "status": item.status, "summary": item.summary}
                for item in checks
            ],
            "runs": [
                {
                    "id": row[0], "kind": row[1], "status": row[3],
                    "started_at": row[5], "finished_at": row[6],
                }
                for row in runs
            ],
            "channels": [
                {"channel": row[0], "status": row[1], "updated_at": row[2]}
                for row in channel_rows
            ],
            "alerts": alerts,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dashboard summary unavailable") from exc
