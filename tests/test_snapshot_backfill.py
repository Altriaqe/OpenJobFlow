from datetime import date
from unittest.mock import Mock

import pytest

from jobflow import snapshot_backfill
from jobflow.models.snapshot import SnapshotHeader


def request() -> snapshot_backfill.VerifiedBackfillRequest:
    return snapshot_backfill.VerifiedBackfillRequest(
        batch_id=42,
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=1,
        details_included=False,
    )


def raw_job(job_id: str = "job-1", *, location: str = "上海·浦东新区") -> dict[str, str]:
    return {
        "job_id": job_id,
        "title": "AI Agent 工程师",
        "boss_name": "示例公司",
        "location": location,
        "job_link": f"https://example.com/{job_id}",
        "salary": "20-30K",
        "skills": "Python|RAG",
    }


def candidate(**changes) -> snapshot_backfill.BatchCandidate:
    values = {
        "batch_id": 42,
        "status": "succeeded",
        "row_count": 1,
        "raw_jobs": (raw_job(),),
    }
    values.update(changes)
    return snapshot_backfill.BatchCandidate(**values)


class AuditCursor:
    def __init__(self) -> None:
        self.executed = []

    def execute(self, sql, params) -> None:
        self.executed.append((sql, params))

    def fetchall(self):
        return [(42, "succeeded", date(2026, 8, 18), 1, 1, 1)]


def test_audit_is_read_only_and_prints_non_secret_summary(monkeypatch, capsys) -> None:
    connection = Mock()
    connection.cursor.return_value = AuditCursor()
    monkeypatch.setattr(snapshot_backfill, "connect_postgres", lambda: connection)

    result = snapshot_backfill.main(
        ["audit", "--start-date", "2026-08-01", "--end-date", "2026-08-18"]
    )

    assert result == 0
    assert "batch_id" in capsys.readouterr().out
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    sql = connection.cursor.return_value.executed[0][0]
    assert "payload ->> 'location'" in sql
    assert "SELECT" in sql and "error_message" not in sql


def test_backfill_requires_explicit_scope_confirmation(monkeypatch, capsys) -> None:
    connect = Mock()
    monkeypatch.setattr(snapshot_backfill, "connect_postgres", connect)

    result = snapshot_backfill.main(
        [
            "backfill",
            "--batch-id",
            "42",
            "--snapshot-date",
            "2026-08-18",
            "--search-keyword",
            "AI Agent",
            "--cities",
            "上海,北京,杭州,深圳",
            "--pages-per-city",
            "1",
            "--detail-mode",
            "no-detail",
        ]
    )

    assert result == 2
    assert "--confirm-scope" in capsys.readouterr().err
    connect.assert_not_called()


@pytest.mark.parametrize(
    ("unsafe", "message"),
    [
        (candidate(status="failed"), "succeeded"),
        (candidate(row_count=2), "row count"),
        (candidate(row_count=0, raw_jobs=()), "non-empty"),
        (candidate(raw_jobs=(raw_job(location="广州·天河区"),)), "undeclared city"),
        (candidate(row_count=2, raw_jobs=(raw_job(), raw_job())), "duplicate"),
    ],
)
def test_backfill_rejects_unsafe_candidate_without_commit(
    unsafe, message: str, monkeypatch
) -> None:
    connection = Mock()
    monkeypatch.setattr(snapshot_backfill, "get_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(snapshot_backfill, "_load_batch_candidate", lambda *_args: unsafe)

    with pytest.raises(ValueError, match=message):
        snapshot_backfill.backfill_verified_batch(connection, request())

    connection.commit.assert_not_called()


def test_verified_backfill_inserts_pending_delivery_without_telegram(monkeypatch) -> None:
    connection = Mock()
    insert = Mock(return_value=17)
    monkeypatch.setattr(snapshot_backfill, "get_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(snapshot_backfill, "_load_batch_candidate", lambda *_args: candidate())
    monkeypatch.setattr(snapshot_backfill, "insert_snapshot", insert)

    snapshot_id = snapshot_backfill.backfill_verified_batch(connection, request())

    assert snapshot_id == 17
    insert.assert_called_once()
    assert insert.call_args.kwargs["metadata"].pages_per_city == 1
    connection.commit.assert_called_once_with()
    assert "jobflow.channels.telegram" not in snapshot_backfill.__dict__


def test_existing_same_batch_snapshot_is_idempotent_without_commit(monkeypatch) -> None:
    existing = SnapshotHeader(
        id=17,
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        batch_id=42,
        city_count=4,
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=1,
        details_included=False,
    )
    connection = Mock()
    monkeypatch.setattr(snapshot_backfill, "get_snapshot", lambda *_args, **_kwargs: existing)

    assert snapshot_backfill.backfill_verified_batch(connection, request()) == 17
    connection.commit.assert_not_called()


def test_existing_same_batch_with_different_scope_is_rejected(monkeypatch) -> None:
    existing = SnapshotHeader(
        id=17,
        snapshot_date=date(2026, 8, 18),
        search_keyword="AI Agent",
        batch_id=42,
        city_count=4,
        cities=("上海", "北京", "杭州", "深圳"),
        pages_per_city=3,
        details_included=False,
    )
    connection = Mock()
    monkeypatch.setattr(snapshot_backfill, "get_snapshot", lambda *_args, **_kwargs: existing)

    with pytest.raises(ValueError, match="scope"):
        snapshot_backfill.backfill_verified_batch(connection, request())

    connection.commit.assert_not_called()
