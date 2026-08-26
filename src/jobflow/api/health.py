"""健康检查入口：区分进程存活和数据库就绪。"""

from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection

router = APIRouter()


@router.get("/health")
def get_health():
    """返回进程存活状态，不依赖数据库。"""
    return {"status": "ok"}


@router.get("/ready")
def get_readiness(connection=Depends(get_connection)):
    """执行 SELECT 1 探针，区分 API 存活与数据库就绪。"""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        if cursor.fetchone() != (1,):
            raise RuntimeError("unexpected readiness result")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return {"status": "ready"}
