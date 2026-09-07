"""阶段状态只读 API：复用平台阶段定义和服务器检查证据。"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection
from jobflow.db.operations import list_recent_checks
from jobflow.operations.models import load_stage_definitions
from jobflow.operations.stages import build_stage_snapshot, stage_evidence

router = APIRouter(prefix="/operations")


@router.get("/stages")
def get_stage_statuses(connection=Depends(get_connection)):
    """返回八个阶段的定义和基于最近检查结果计算出的状态。"""
    try:
        config_path = Path(__file__).parents[3] / "config" / "platform_stages.yaml"
        definitions = load_stage_definitions(config_path)
        checks = list_recent_checks(connection)
        snapshot = build_stage_snapshot(definitions, stage_evidence(checks))
        return [
            {
                "id": item.definition.id,
                "name": item.definition.name,
                "goal": item.definition.goal,
                "acceptance": item.definition.acceptance,
                "state": item.state.value,
            }
            for item in snapshot
        ]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="stage status unavailable") from exc
