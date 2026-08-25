from pathlib import Path


def test_raw_job_records_migration_defines_table_and_constraints():
    migration_path = Path("migrations/003_create_raw_job_records.sql")

    assert migration_path.exists()

    sql = migration_path.read_text(encoding="utf-8")

    assert "CREATE SCHEMA IF NOT EXISTS raw" in sql
    assert "CREATE TABLE IF NOT EXISTS raw.job_records" in sql
    assert "batch_id BIGINT NOT NULL" in sql
    assert "REFERENCES ops.batches (id)" in sql
    assert "payload JSONB NOT NULL" in sql
    assert "ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP" in sql
    assert "UNIQUE (batch_id, source, external_id)" in sql
