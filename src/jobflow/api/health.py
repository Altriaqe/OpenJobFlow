from fastapi import APIRouter, Depends, HTTPException

from jobflow.api.dependencies import get_connection

router = APIRouter()


@router.get("/health")
def get_health():
    return {"status": "ok"}


@router.get("/ready")
def get_readiness(connection=Depends(get_connection)):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        if cursor.fetchone() != (1,):
            raise RuntimeError("unexpected readiness result")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return {"status": "ready"}
