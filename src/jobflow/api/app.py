from fastapi import FastAPI

from jobflow.api.analytics import router as analytics_router
from jobflow.api.health import router as health_router
from jobflow.api.reports import router as reports_router


def create_app() -> FastAPI:
    app = FastAPI(title="JobFlow Analytics API")
    app.include_router(health_router)
    app.include_router(analytics_router)
    app.include_router(reports_router)
    return app


app = create_app()
