"""带管理员校验和明确日期的人工投放入口。"""

import os
from collections.abc import Callable
from datetime import date

from jobflow.operations.models import Channel, DeliveryResult


def _check_admin(token: str) -> None:
    expected = os.environ.get("JOBFLOW_ADMIN_TOKEN")
    if not expected or token != expected:
        raise PermissionError("invalid administrator token")


def _deliver(
    channel: Channel, report_date: date, admin_token: str, sender: Callable[[date], None]
) -> DeliveryResult:
    _check_admin(admin_token)
    if not isinstance(report_date, date):
        raise TypeError("report_date must be a date")
    try:
        sender(report_date)
    except Exception as exc:  # noqa: BLE001 - keep dashboard errors safe
        return DeliveryResult(channel, report_date, "failed", type(exc).__name__)
    return DeliveryResult(
        channel, report_date, "sent" if channel == Channel.TELEGRAM else "created"
    )


def manual_telegram_delivery(
    report_date: date, admin_token: str, sender: Callable[[date], None]
) -> DeliveryResult:
    return _deliver(Channel.TELEGRAM, report_date, admin_token, sender)


def manual_wechat_draft(
    report_date: date, admin_token: str, sender: Callable[[date], None]
) -> DeliveryResult:
    return _deliver(Channel.WECHAT, report_date, admin_token, sender)
