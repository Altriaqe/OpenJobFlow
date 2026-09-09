"""按日期查看和保护单渠道投放动作。"""

from datetime import date
import json
from pathlib import Path


STATUS_ACTIONS = {
    "not_sent": ("send",),
    "pending": ("send",),
    "sending": (),
    "creating": (),
    "sent": (),
    "created": (),
    "failed": ("retry",),
    "uncertain": (),
}


def _one(connection, sql: str, params: tuple[object, ...]):
    cursor = connection.cursor()
    cursor.execute(sql, params)
    return cursor.fetchone()


def _snapshot_available(connection, report_date: date) -> bool:
    row = _one(
        connection,
        """
        SELECT EXISTS (
            SELECT 1 FROM core.job_snapshots
            WHERE snapshot_date = %s AND status = 'succeeded'
        )
        """,
        (report_date,),
    )
    return bool(row and row[0])


def _article_available(report_date: date, runtime_root: Path = Path("runtime")) -> bool:
    output_dir = runtime_root / "reports" / report_date.isoformat() / "wechat"
    try:
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    required = ("article.html", "cover.png", "trend.png", "manifest.json")
    return manifest.get("report_date") == report_date.isoformat() and all(
        (output_dir / name).is_file() for name in required
    )


def _channel_rows(connection, report_date: date) -> dict[str, tuple[object, ...]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT channel, status, attempts, updated_at, last_error_type
        FROM ops.report_channel_deliveries
        WHERE report_date = %s
        ORDER BY updated_at DESC
        """,
        (report_date,),
    )
    rows: dict[str, tuple[object, ...]] = {}
    for row in cursor.fetchall():
        channel = "wechat" if str(row[0]).startswith("wechat") else str(row[0])
        rows.setdefault(channel, row[1:])
    return rows


def _telegram_legacy_row(connection, report_date: date):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT d.status, d.text_attempts + d.photo_attempts, d.updated_at,
               d.last_error_type
        FROM ops.report_deliveries AS d
        JOIN core.job_snapshots AS s ON s.id = d.snapshot_id
        WHERE s.snapshot_date = %s
        ORDER BY d.updated_at DESC
        LIMIT 1
        """,
        (report_date,),
    )
    return cursor.fetchone()


def _wechat_draft_row(connection, report_date: date):
    return _one(
        connection,
        """
        SELECT status, updated_at, error_code
        FROM ops.wechat_draft_jobs
        WHERE report_date = %s
        """,
        (report_date,),
    )


def _safe_channel(channel: str, status: str, attempts: int, updated_at, error_code=None):
    return {
        "channel": channel,
        "status": status,
        "attempts": attempts,
        "updated_at": updated_at,
        "error_code": error_code,
        "actions": list(STATUS_ACTIONS.get(status, ())),
    }


def build_delivery_workbench(
    connection, *, report_date: date, today: date
) -> dict[str, object]:
    """返回指定日期的安全投放快照，不调用外部服务。"""
    if report_date > today:
        return {
            "date": report_date.isoformat(),
            "date_state": "future",
            "snapshot_available": False,
            "article_available": False,
            "stages": [],
            "channels": [],
        }

    snapshot_available = _snapshot_available(connection, report_date)
    article_available = _article_available(report_date)
    channel_rows = _channel_rows(connection, report_date)
    telegram = channel_rows.get("telegram")
    if telegram is None:
        legacy = _telegram_legacy_row(connection, report_date)
        legacy_statuses = {
            "completed": "sent",
            "completed_text_uncertain": "uncertain",
            "text_sent": "sending",
            "partial_failed": "failed",
            "failed": "failed",
        }
        telegram = (
            (legacy_statuses.get(legacy[0], "not_sent"), legacy[1], legacy[2], legacy[3])
            if legacy
            else ("not_sent", 0, None, None)
        )
    wechat = channel_rows.get("wechat")
    draft = _wechat_draft_row(connection, report_date)
    if draft is not None:
        wechat = (draft[0], 0, draft[1], draft[2])
    elif wechat is None:
        wechat = ("not_sent", 0, None, None)

    return {
        "date": report_date.isoformat(),
        "date_state": "today" if report_date == today else "past",
        "snapshot_available": snapshot_available,
        "article_available": article_available,
        "stages": [
            {"id": "snapshot", "status": "ready" if snapshot_available else "missing"},
            {"id": "article", "status": "ready" if article_available else "missing"},
        ],
        "channels": [
            _safe_channel("telegram", telegram[0], telegram[1], telegram[2], telegram[3]),
            _safe_channel("wechat", wechat[0], wechat[1], wechat[2], wechat[3]),
        ],
    }


def assert_delivery_allowed(
    connection,
    *,
    report_date: date,
    channel: str,
    today: date,
    confirm_uncertain: bool = False,
) -> None:
    """在进入既有投放服务前执行日期、快照和渠道状态校验。"""
    if report_date > today:
        raise ValueError("future date is not actionable")
    workbench = build_delivery_workbench(connection, report_date=report_date, today=today)
    if not workbench["snapshot_available"]:
        raise ValueError("snapshot is not available")
    if channel == "wechat" and not workbench["article_available"]:
        raise ValueError("article package is not available")
    selected = next((row for row in workbench["channels"] if row["channel"] == channel), None)
    if selected is None:
        raise ValueError("unsupported delivery channel")
    status = selected["status"]
    if status in {"sent", "created", "sending", "creating"}:
        raise ValueError(f"channel delivery cannot be claimed from {status}")
    if status == "uncertain" and not confirm_uncertain:
        raise ValueError("uncertain delivery requires confirmation")
    if status not in {"not_sent", "pending", "failed", "uncertain"}:
        raise ValueError("channel delivery is not actionable")


__all__ = ["assert_delivery_allowed", "build_delivery_workbench"]
