from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from jobflow.operations.delivery_workbench import (
    assert_delivery_allowed,
    build_delivery_workbench,
)


TODAY = date(2026, 9, 9)
REPORT_DATE = date(2026, 9, 8)


def _connection(*, snapshot=True, telegram=None, wechat=None):
    connection = Mock()
    cursor = connection.cursor.return_value

    def execute(sql, _params):
        if "core.job_snapshots" in sql and "EXISTS" in sql:
            cursor.fetchone.return_value = (snapshot,)
        elif "report_channel_deliveries" in sql:
            cursor.fetchall.return_value = telegram or ([] if wechat is None else [])
        elif "wechat_draft_jobs" in sql:
            cursor.fetchone.return_value = wechat
        elif "FROM ops.report_deliveries" in sql:
            cursor.fetchone.return_value = None

    cursor.execute.side_effect = execute
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return connection


def test_future_date_is_not_actionable():
    result = build_delivery_workbench(
        _connection(), report_date=date(2026, 9, 10), today=TODAY
    )
    assert result["date_state"] == "future"
    assert result["snapshot_available"] is False
    assert result["channels"] == []


def test_past_date_reuses_existing_snapshot(monkeypatch, tmp_path: Path):
    output = tmp_path / "runtime" / "reports" / REPORT_DATE.isoformat() / "wechat"
    output.mkdir(parents=True)
    (output / "manifest.json").write_text(
        '{"report_date": "2026-09-08"}', encoding="utf-8"
    )
    for name in ("article.html", "cover.png", "trend.png"):
        (output / name).write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    result = build_delivery_workbench(_connection(), report_date=REPORT_DATE, today=TODAY)
    assert result["date_state"] == "past"
    assert result["snapshot_available"] is True
    assert result["article_available"] is True
    assert result["channels"][0]["actions"] == ["send"]


@pytest.mark.parametrize("status, confirm, allowed", [("sent", False, False), ("failed", False, True), ("uncertain", False, False), ("uncertain", True, True)])
def test_delivery_policy(status, confirm, allowed):
    connection = _connection(telegram=[("telegram", status, 1, None, "network")])
    if allowed:
        assert_delivery_allowed(
            connection,
            report_date=REPORT_DATE,
            channel="telegram",
            today=TODAY,
            confirm_uncertain=confirm,
        )
    else:
        with pytest.raises(ValueError):
            assert_delivery_allowed(
                connection,
                report_date=REPORT_DATE,
                channel="telegram",
                today=TODAY,
                confirm_uncertain=confirm,
            )
