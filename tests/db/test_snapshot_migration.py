from pathlib import Path


def test_snapshot_migration_exists() -> None:
    migration_path = Path("migrations/006_add_daily_job_snapshots.sql")

    assert migration_path.exists()


def test_snapshot_migration_defines_history_and_delivery_contract() -> None:
    migration_path = Path("migrations/006_add_daily_job_snapshots.sql")
    sql = migration_path.read_text(encoding="utf-8")
    normalized = " ".join(sql.split())

    assert "CREATE TABLE IF NOT EXISTS core.job_snapshots" in normalized
    assert "UNIQUE (snapshot_date, search_keyword)" in normalized
    assert "batch_id BIGINT NOT NULL UNIQUE" in normalized
    assert "cities TEXT[] NOT NULL" in normalized
    assert "details_included BOOLEAN NOT NULL" in normalized
    assert "city_count = cardinality(cities)" in normalized

    assert "CREATE TABLE IF NOT EXISTS core.job_snapshot_items" in normalized
    assert "PRIMARY KEY (snapshot_id, source, external_id)" in normalized
    assert "REFERENCES core.job_snapshots (id) ON DELETE CASCADE" in normalized

    assert "CREATE TABLE IF NOT EXISTS ops.report_deliveries" in normalized
    assert "partial_failed" in normalized
    assert "text_message_id BIGINT" in normalized
    assert "photo_message_id BIGINT" in normalized
    assert "text_attempts SMALLINT NOT NULL DEFAULT 0" in normalized
    assert "photo_attempts SMALLINT NOT NULL DEFAULT 0" in normalized
    assert "report_deliveries_message_ids_check" in normalized
    assert "report_deliveries_state_check" in normalized
    assert "status = 'completed'" in normalized


def test_uncertain_delivery_migration_is_idempotent_and_complete() -> None:
    migration_path = Path("migrations/007_add_uncertain_report_delivery_states.sql")
    sql = migration_path.read_text(encoding="utf-8")
    normalized = " ".join(sql.split())

    for status in (
        "text_sending",
        "text_failed",
        "text_uncertain",
        "photo_sending",
        "photo_failed",
        "photo_uncertain",
        "completed_text_uncertain",
    ):
        assert f"'{status}'" in normalized
    assert "DROP CONSTRAINT IF EXISTS report_deliveries_status_check" in normalized
    assert "DROP CONSTRAINT IF EXISTS report_deliveries_state_check" in normalized
    assert "ADD CONSTRAINT report_deliveries_status_check" in normalized
    assert "ADD CONSTRAINT report_deliveries_state_check" in normalized
    assert "completed_text_uncertain" in normalized
    assert "text_message_id IS NULL" in normalized
    assert "photo_message_id IS NOT NULL" in normalized
