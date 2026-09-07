"""运行中心的只读检查记录 API。"""

from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection
from jobflow.db.operations import list_recent_checks, list_recent_runs

router = APIRouter(prefix="/operations")


@router.get("/checks")
def get_recent_checks(connection=Depends(get_connection)):
    try:
        return [
            {
                "name": item.name,
                "status": item.status,
                "summary": item.summary,
                "error": item.error,
            }
            for item in list_recent_checks(connection)
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
