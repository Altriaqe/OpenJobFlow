"""FastAPI 依赖：集中创建数据库连接，保证路由层可替换测试。"""

from fastapi import HTTPException

from jobflow.db.connection import connect_postgres


def get_connection():
    """创建请求范围连接，并在依赖结束时回滚未提交操作后关闭。"""
    connection = None
    try:
        connection = connect_postgres()
        yield connection
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()
