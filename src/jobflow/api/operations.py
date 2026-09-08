"""运行中心的只读检查记录 API。"""

from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.auth import require_admin
from jobflow.api.dependencies import get_connection
from jobflow.db.operations import (
    create_operation_run,
    finish_operation_run,
    list_recent_checks,
    list_recent_runs,
    record_check_result,
)
from jobflow.operations.checks import run_server_checks
from jobflow.operations.probes import build_dashboard_probes

router = APIRouter(prefix="/operations")


@router.get("/checks")
def get_recent_checks(connection=Depends(get_connection)):
    try:
        checks = list_recent_checks(connection)
        latest_by_name = {}
        for item in checks:
            latest_by_name.setdefault(item.name, item)
        return [
            {
                "name": item.name,
                "status": item.status,
                "summary": item.summary,
                "error": item.error,
            }
            for item in latest_by_name.values()
        ]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="operation checks unavailable") from exc


@router.get("/runs")
def get_recent_runs(connection=Depends(get_connection)):
    try:
        return [
            {
                "id": row[0],
                "kind": row[1],
                "report_date": row[2],
                "status": row[3],
                "error_message": row[4],
                "started_at": row[5],
                "finished_at": row[6],
            }
            for row in list_recent_runs(connection)
        ]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="operation runs unavailable") from exc


@router.post("/checks/run", dependencies=[Depends(require_admin)])
def run_checks(connection=Depends(get_connection)):
    try:
        operation_id = create_operation_run(connection, kind="server_check")
        results = run_server_checks(build_dashboard_probes(connection))
        for result in results:
            record_check_result(connection, operation_id=operation_id, result=result)
        status = "succeeded" if all(item.status == "succeeded" for item in results) else "failed"
        finish_operation_run(connection, operation_id=operation_id, status=status)
        connection.commit()
        return {"operation_id": operation_id, "status": status}
    except Exception as exc:
        connection.rollback()
        raise HTTPException(status_code=503, detail="server checks unavailable") from exc
