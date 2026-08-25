from pathlib import Path


def test_mart_city_job_counts_migration_defines_view():
    """测试 mart_city_job_counts_migration 是否定义了视图"""
    migration_path = Path("migrations/004_create_mart_city_job_counts.sql")

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")
    normalized_sql = " ".join(sql.split())

    assert "CREATE SCHEMA IF NOT EXISTS mart" in normalized_sql
    assert "CREATE OR REPLACE VIEW mart.city_job_counts" in normalized_sql
    assert "city" in normalized_sql
    assert "COUNT(*) AS job_count" in normalized_sql
    assert "FROM core.jobs" in normalized_sql
    assert "GROUP BY city" in normalized_sql
