import os

import psycopg


class DatabaseConfigError(Exception):
    # 数据库配置错误
    pass


def connect_postgres():
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")

    required_config = {
        "POSTGRES_HOST": host,
        "POSTGRES_PORT": port,
        "POSTGRES_DB": db,
        "POSTGRES_USER": user,
        "POSTGRES_PASSWORD": password,
    }

    for variable_name, value in required_config.items():
        if not value:
            raise DatabaseConfigError(f"缺少环境变量 {variable_name}")

    return psycopg.connect(
        password=password,
        host=host,
        port=port,
        dbname=db,
        user=user,
    )
