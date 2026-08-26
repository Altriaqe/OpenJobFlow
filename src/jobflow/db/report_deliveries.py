"""通用报告渠道投递状态：用行锁防止同一天同渠道重复发送。"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ChannelDelivery:
    report_date: date
    report_key: str
    channel: str
    status: str
    external_message_id: str | None
    attempts: int
    last_error_type: str | None


def ensure_delivery(connection, *, report_date: date, report_key: str, channel: str) -> None:
    """幂等创建 pending 状态；已存在时保持原状态不变。"""
    connection.cursor().execute(
        """
        INSERT INTO ops.report_channel_deliveries (report_date, report_key, channel)
        VALUES (%s, %s, %s)
        ON CONFLICT (report_date, report_key, channel) DO NOTHING
        """,
        (report_date, report_key, channel),
    )


def get_delivery_for_update(
    connection, *, report_date: date, report_key: str, channel: str
) -> ChannelDelivery | None:
    """锁定一条渠道状态，锁只影响指定渠道，不阻塞其他渠道。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT report_date, report_key, channel, status,
               external_message_id, attempts, last_error_type
        FROM ops.report_channel_deliveries
        WHERE report_date = %s AND report_key = %s AND channel = %s
        FOR UPDATE
        """,
        (report_date, report_key, channel),
    )
    row = cursor.fetchone()
    return None if row is None else ChannelDelivery(*row)


def get_channel_delivery(
    connection, *, report_date: date, report_key: str, channel: str
) -> ChannelDelivery | None:
    """只读查询渠道状态，供状态 API 使用，不获取行锁。"""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT report_date, report_key, channel, status,
               external_message_id, attempts, last_error_type
        FROM ops.report_channel_deliveries
        WHERE report_date = %s AND report_key = %s AND channel = %s
        """,
        (report_date, report_key, channel),
    )
    row = cursor.fetchone()
    return None if row is None else ChannelDelivery(*row)


def claim_delivery(
    connection,
    *,
    report_date: date,
    report_key: str,
    channel: str,
    allow_uncertain: bool = False,
) -> ChannelDelivery:
    """认领发送权；sent/sending 禁止重复，uncertain 仅显式允许时重试。"""
    ensure_delivery(connection, report_date=report_date, report_key=report_key, channel=channel)
    delivery = get_delivery_for_update(
        connection, report_date=report_date, report_key=report_key, channel=channel
    )
    if delivery is None:
        raise RuntimeError("channel delivery state was not created")
    allowed = {"pending", "failed"}
    if allow_uncertain:
        allowed.add("uncertain")
    if delivery.status not in allowed:
        raise ValueError(f"channel delivery cannot be claimed from {delivery.status}")
    connection.cursor().execute(
        """
        UPDATE ops.report_channel_deliveries
        SET status = 'sending', attempts = attempts + 1,
            last_error_type = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE report_date = %s AND report_key = %s AND channel = %s
        """,
        (report_date, report_key, channel),
    )
    return delivery


def record_delivery_result(
    connection,
    *,
    report_date: date,
    report_key: str,
    channel: str,
    status: str,
    external_message_id: str | None = None,
    error_type: str | None = None,
) -> None:
    """把已认领状态转换为 sent、failed 或 uncertain。"""
    if status not in {"sent", "failed", "uncertain"}:
        raise ValueError("invalid delivery result status")
    connection.cursor().execute(
        """
        UPDATE ops.report_channel_deliveries
        SET status = %s, external_message_id = %s,
            last_error_type = %s, updated_at = CURRENT_TIMESTAMP
        WHERE report_date = %s AND report_key = %s AND channel = %s
          AND status = 'sending'
        """,
        (status, external_message_id, error_type, report_date, report_key, channel),
    )
