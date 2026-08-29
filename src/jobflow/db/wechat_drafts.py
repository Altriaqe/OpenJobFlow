"""微信公众号草稿任务状态：独立于 Telegram 的幂等记录。"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class WechatDraftStatus:
    report_date: date
    status: str
    draft_media_id: str | None
    cover_media_id: str | None
    trend_media_id: str | None
    error_code: str | None
    error_message: str | None


def claim_wechat_draft(connection, *, report_date: date) -> bool:
    """为日期预占草稿创建权；重复运行时不重复创建。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO ops.wechat_draft_jobs (report_date, status)
        VALUES (%s, 'uploading')
        ON CONFLICT (report_date) DO NOTHING
        RETURNING id
        """,
        (report_date,),
    )
    return cursor.fetchone() is not None


def record_wechat_draft_created(
    connection,
    *,
    report_date: date,
    draft_media_id: str,
    cover_media_id: str,
    trend_media_id: str | None,
) -> None:
    """记录微信已接受草稿，ID 只作为平台标识保存。"""
    connection.cursor().execute(
        """
        UPDATE ops.wechat_draft_jobs
        SET status = 'created', draft_media_id = %s,
            cover_media_id = %s, trend_media_id = %s,
            error_code = NULL, error_message = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE report_date = %s AND status = 'uploading'
        """,
        (draft_media_id, cover_media_id, trend_media_id, report_date),
    )


def record_wechat_draft_failed(
    connection,
    *,
    report_date: date,
    error_code: str,
    error_message: str,
) -> None:
    """记录脱敏错误；调用方不得把 token 或完整 URL 传入。"""
    connection.cursor().execute(
        """
        UPDATE ops.wechat_draft_jobs
        SET status = 'failed', error_code = %s, error_message = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE report_date = %s AND status = 'uploading'
        """,
        (error_code, error_message, report_date),
    )


def get_wechat_draft_status(connection, *, report_date: date) -> WechatDraftStatus | None:
    """读取草稿状态，供状态接口或运维检查使用。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT report_date, status, draft_media_id, cover_media_id,
               trend_media_id, error_code, error_message
        FROM ops.wechat_draft_jobs
        WHERE report_date = %s
        """,
        (report_date,),
    )
    row = cursor.fetchone()
    return None if row is None else WechatDraftStatus(*row)
