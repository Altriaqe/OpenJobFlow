"""FastAPI 依赖：集中创建数据库连接，保证路由层可替换测试。"""

from jobflow.db.connection import connect_postgres


def get_connection():
    """创建请求范围连接，并在依赖结束时回滚未提交操作后关闭。"""
    connection = connect_postgres()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
