"""分析 API：鉴权后读取 mart 聚合视图，不直接暴露 raw/core 明细。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from jobflow.api.dependencies import get_connection
from jobflow.db.analytics import (
    list_city_job_counts,
    list_city_salary_stats,
    list_skill_job_counts,
)

router = APIRouter(prefix="/analytics")


@router.get("/cities")
def get_city_job_counts(
    limit: int = Query(default=20, ge=1, le=100),
    connection=Depends(get_connection),
):
    """读取城市岗位数量；数据库异常统一映射为 HTTP 503。"""
    try:
        return list_city_job_counts(connection, limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="analytics database unavailable",
        ) from exc


@router.get("/salaries/cities")
def get_city_salary_stats(
    limit: int = Query(default=20, ge=1, le=100),
    connection=Depends(get_connection),
):
    """读取城市薪资统计；limit 由 Query 约束在 1 到 100。"""
    try:
        return list_city_salary_stats(connection, limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="analytics database unavailable",
        ) from exc


@router.get("/skills")
def get_skill_job_counts(
    limit: int = Query(default=20, ge=1, le=100),
    connection=Depends(get_connection),
):
    """读取技能覆盖数量，接口只暴露 mart 聚合结果。"""
    try:
        return list_skill_job_counts(connection, limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="analytics database unavailable",
        ) from exc
