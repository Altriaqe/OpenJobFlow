"""FastAPI 应用入口：组装健康检查、分析和报告路由。"""

from fastapi import FastAPI

from jobflow.api.analytics import router as analytics_router
from jobflow.api.health import router as health_router
from jobflow.api.reports import router as reports_router


def create_app() -> FastAPI:
    """创建应用实例，便于生产启动和测试分别获得干净的路由容器。"""
    app = FastAPI(title="JobFlow Analytics API")
    # 路由按职责拆分；这里仅负责注册，不承载业务逻辑。
    app.include_router(health_router)
    app.include_router(analytics_router)
    app.include_router(reports_router)
    return app


app = create_app()
