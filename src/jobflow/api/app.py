"""FastAPI 应用入口：组装健康检查、分析和报告路由。"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobflow.api.analytics import router as analytics_router
from jobflow.api.dashboard import router as dashboard_router
from jobflow.api.health import router as health_router
from jobflow.api.operations import router as operations_router
from jobflow.api.reports import router as reports_router
from jobflow.api.stages import router as stages_router


def create_app() -> FastAPI:
    """创建应用实例，便于生产启动和测试分别获得干净的路由容器。"""
    app = FastAPI(title="JobFlow Analytics API")
    origins = [
        origin.strip()
        for origin in os.getenv(
            "JOBFLOW_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )
    # 路由按职责拆分；这里仅负责注册，不承载业务逻辑。
    app.include_router(health_router)
    app.include_router(analytics_router)
    app.include_router(dashboard_router)
    app.include_router(operations_router)
    app.include_router(reports_router)
    app.include_router(stages_router)
    return app


app = create_app()
