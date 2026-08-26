from pathlib import Path


def test_channel_delivery_migration_has_unique_key_and_states():
    sql = Path("migrations/009_add_report_channel_deliveries.sql").read_text(encoding="utf-8")

    assert "UNIQUE (report_date, report_key, channel)" in sql
    assert "'pending', 'sending', 'sent', 'failed', 'uncertain'" in sql
    assert "external_message_id" in sql
