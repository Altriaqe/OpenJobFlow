from datetime import date
from unittest.mock import Mock

from jobflow.db.wechat_drafts import (
    WechatDraftStatus,
    claim_wechat_draft,
    get_wechat_draft_status,
    record_wechat_draft_created,
    record_wechat_draft_failed,
)


def test_claim_returns_true_only_when_inserted():
    cursor = Mock()
    cursor.fetchone.return_value = (1,)
    connection = Mock()
    connection.cursor.return_value = cursor

    assert claim_wechat_draft(connection, report_date=date(2026, 8, 29)) is True
    assert "ON CONFLICT (report_date) DO NOTHING" in cursor.execute.call_args.args[0]

    cursor.fetchone.return_value = None
    assert claim_wechat_draft(connection, report_date=date(2026, 8, 29)) is False


def test_record_created_updates_only_uploading_row():
    connection = Mock()
    cursor = Mock()
    connection.cursor.return_value = cursor

    record_wechat_draft_created(
        connection,
        report_date=date(2026, 8, 29),
        draft_media_id="draft-id",
        cover_media_id="cover-id",
        trend_media_id="trend-id",
    )

    sql = cursor.execute.call_args.args[0]
    assert "status = 'created'" in sql
    assert "status = 'uploading'" in sql


def test_record_failed_is_deprecated_and_read_status_is_safe():
    connection = Mock()
    cursor = Mock()
    connection.cursor.return_value = cursor
    record_wechat_draft_failed(
        connection,
        report_date=date(2026, 8, 29),
        error_code="permission_denied",
        error_message="微信接口拒绝请求",
    )
    assert "status = 'failed'" in cursor.execute.call_args.args[0]

    status = WechatDraftStatus(
        date(2026, 8, 29), "created", "draft", "cover", "trend", None, None
    )
    cursor.fetchone.return_value = tuple(status.__dict__.values())
    assert get_wechat_draft_status(connection, report_date=status.report_date) == status
