"""运营看板的统一只读快照。"""

from pathlib import Path

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection
from jobflow.db.operations import list_recent_checks, list_recent_runs
from jobflow.operations.models import load_stage_definitions
from jobflow.operations.stages import build_stage_snapshot, stage_evidence

router = APIRouter(prefix="/dashboard")


@router.get("/deliveries")
def get_delivery_statuses(snapshot_date: date, connection=Depends(get_connection)):
    try:
        cursor = connection.cursor()
        cursor.execute(
            """SELECT channel, status, attempts, updated_at
               FROM ops.report_channel_deliveries
               WHERE report_date = %s ORDER BY updated_at DESC""",
            (snapshot_date,),
        )
        latest = {}
        for channel, status, attempts, updated_at in cursor.fetchall():
            normalized = "wechat" if channel.startswith("wechat") else channel
            latest.setdefault(normalized, (status, attempts, updated_at))
        cursor.execute(
            """SELECT 'telegram', d.status, d.text_attempts + d.photo_attempts, d.updated_at
               FROM ops.report_deliveries AS d
               JOIN core.job_snapshots AS s ON s.id = d.snapshot_id
               WHERE s.snapshot_date = %s
               ORDER BY d.updated_at DESC""",
            (snapshot_date,),
        )
        telegram_status = {
            "completed": "sent",
            "completed_text_uncertain": "uncertain",
            "text_sent": "sending",
        }
        for channel, status, attempts, updated_at in cursor.fetchall():
            latest.setdefault(channel, (telegram_status.get(status, status), attempts, updated_at))
        return [
            {"channel": channel, "status": row[0], "attempts": row[1], "updated_at": row[2]}
            for channel, row in latest.items()
        ]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="delivery status unavailable") from exc


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
            """SELECT id, row_count, finished_at, status
               FROM ops.batches
               ORDER BY id DESC LIMIT 7"""
        )
        batch_trend = cursor.fetchall()
        cursor.execute(
            """SELECT channel, status, updated_at
               FROM ops.report_channel_deliveries
               ORDER BY updated_at DESC"""
        )
        channel_rows = cursor.fetchall()
        latest_channels = {}
        for channel, status, updated_at in channel_rows:
            normalized = "wechat" if channel.startswith("wechat") else channel
            latest_channels.setdefault(normalized, (status, updated_at))
        cursor.execute(
            """SELECT city, job_count
               FROM mart.city_job_counts
               ORDER BY job_count DESC, city ASC LIMIT 5"""
        )
        city_counts = cursor.fetchall()
        cursor.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN status IN ('sent', 'created') THEN 1 ELSE 0 END), 0),
                 COUNT(*)
               FROM ops.report_channel_deliveries"""
        )
        delivery_totals = cursor.fetchone()
        checks = list_recent_checks(connection)
        latest_checks = {}
        for item in checks:
            latest_checks.setdefault(item.name, item)
        checks = tuple(latest_checks.values())
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
            "trend": [
                {"id": row[0], "row_count": row[1], "finished_at": row[2], "status": row[3]}
                for row in reversed(batch_trend)
            ],
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
                {"channel": channel, "status": row[0], "updated_at": row[1]}
                for channel, row in latest_channels.items()
            ],
            "city_counts": [{"city": row[0], "job_count": row[1]} for row in city_counts],
            "delivery_totals": {
                "successful": delivery_totals[0],
                "total": delivery_totals[1],
            },
            "alerts": alerts,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dashboard summary unavailable") from exc
