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
    try:
        return list_skill_job_counts(connection, limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="analytics database unavailable",
        ) from exc
