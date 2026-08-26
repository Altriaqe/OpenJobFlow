"""单关键词日报服务：协调快照读取、比较、文字生成和 Telegram 投递。"""

from collections.abc import Callable
from datetime import date, timedelta

from jobflow.channels.telegram import (
    TelegramDeliveryError,
    TelegramReceipt,
    send_telegram_photo,
    send_telegram_text,
)
from jobflow.db.snapshots import (
    get_delivery,
    get_snapshot,
    list_dated_snapshots,
    list_snapshot_items,
    record_photo_failure,
    record_photo_sent,
    record_text_failure,
    record_text_sent,
)
from jobflow.models.snapshot import SnapshotHeader, WeeklyComparison
from jobflow.reports.charts import build_city_share_png
from jobflow.reports.comparison import compare_complete_weeks, compare_daily
from jobflow.reports.daily_brief import build_daily_brief


class DailySnapshotNotFound(Exception):
    pass


class DailyReportStateError(Exception):
    pass


def get_daily_report_status(
    connection,
    *,
    snapshot_date: date,
    keyword: str,
) -> dict[str, object]:
    header = get_snapshot(
        connection,
        snapshot_date=snapshot_date,
        search_keyword=keyword,
    )
    if header is None:
        raise DailySnapshotNotFound("daily snapshot not found")
    delivery = get_delivery(connection, header.id)
    if delivery is None:
        raise DailyReportStateError("daily delivery state not found")
    return {
        "snapshot_id": header.id,
        "snapshot_date": header.snapshot_date.isoformat(),
        "keyword": header.search_keyword,
        "status": delivery.status,
        "text_sent": delivery.text_message_id is not None,
        "photo_sent": delivery.photo_message_id is not None,
        "text_attempts": delivery.text_attempts,
        "photo_attempts": delivery.photo_attempts,
        "last_error_type": delivery.last_error_type,
    }


def _same_scope(left: SnapshotHeader, right: SnapshotHeader) -> bool:
    return left.scope_key == right.scope_key


def load_weekly_comparison_if_sunday(
    connection,
    *,
    report_date: date,
    keyword: str,
    current_header: SnapshotHeader,
) -> WeeklyComparison | None:
    if report_date.weekday() != 6:
        return None

    current_start = report_date - timedelta(days=6)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    for offset in range(14):
        expected_date = previous_start + timedelta(days=offset)
        header = get_snapshot(
            connection,
            snapshot_date=expected_date,
            search_keyword=keyword,
        )
        if header is None or not _same_scope(current_header, header):
            return None

    current_days = list_dated_snapshots(
        connection,
        start_date=current_start,
        end_date=report_date,
        search_keyword=keyword,
    )
    previous_days = list_dated_snapshots(
        connection,
        start_date=previous_start,
        end_date=previous_end,
        search_keyword=keyword,
    )
    return compare_complete_weeks(
        report_date=report_date,
        current_days=current_days,
        previous_days=previous_days,
        cities=current_header.cities,
    )


def _record_failure(
    connection,
    *,
    snapshot_id: int,
    stage: str,
    attempts: int,
) -> None:
    if stage == "text":
        record_text_failure(connection, snapshot_id, "telegram_delivery", attempts)
    elif stage == "photo":
        record_photo_failure(connection, snapshot_id, "telegram_delivery", attempts)
    else:
        raise ValueError("unsupported delivery stage")
    connection.commit()


def send_daily_report(
    connection,
    *,
    snapshot_date: date,
    keyword: str,
    text_sender: Callable[[str], TelegramReceipt] = send_telegram_text,
    photo_sender: Callable[[bytes], TelegramReceipt] = send_telegram_photo,
) -> dict[str, object]:
    """生成并分阶段发送一份可安全重入的每日图文简报。"""

    header = get_snapshot(
        connection,
        snapshot_date=snapshot_date,
        search_keyword=keyword,
    )
    if header is None:
        raise DailySnapshotNotFound("daily snapshot not found")
    delivery = get_delivery(connection, header.id)
    if delivery is None:
        raise DailyReportStateError("daily delivery state not found")
    if delivery.status == "completed":
        return {"status": "already_sent", "snapshot_id": header.id}
    if delivery.status not in {"pending", "failed", "text_sent", "partial_failed"}:
        raise DailyReportStateError("unsupported daily delivery state")

    current_items = list_snapshot_items(connection, header.id)
    previous_header = get_snapshot(
        connection,
        snapshot_date=snapshot_date - timedelta(days=1),
        search_keyword=keyword,
    )
    if previous_header is not None and not _same_scope(header, previous_header):
        previous_header = None
    previous_items = (
        None if previous_header is None else list_snapshot_items(connection, previous_header.id)
    )
    daily = compare_daily(current_items, previous_items, cities=header.cities)
    weekly = load_weekly_comparison_if_sunday(
        connection,
        report_date=snapshot_date,
        keyword=keyword,
        current_header=header,
    )
    text = build_daily_brief(
        report_date=snapshot_date,
        keyword=keyword,
        city_count=header.city_count,
        pages_per_city=header.pages_per_city,
        daily=daily,
        weekly=weekly,
    )
    image = build_city_share_png(daily.city_metrics)

    text_message_id = delivery.text_message_id
    if delivery.status in {"pending", "failed"}:
        try:
            text_receipt = text_sender(text)
        except TelegramDeliveryError as exc:
            _record_failure(
                connection,
                snapshot_id=header.id,
                stage="text",
                attempts=exc.attempts,
            )
            raise TelegramDeliveryError(
                "daily report text delivery failed", attempts=exc.attempts
            ) from None
        record_text_sent(
            connection,
            header.id,
            text_receipt.message_id,
            text_receipt.attempts,
        )
        connection.commit()
        text_message_id = text_receipt.message_id

    try:
        photo_receipt = photo_sender(image)
    except TelegramDeliveryError as exc:
        _record_failure(
            connection,
            snapshot_id=header.id,
            stage="photo",
            attempts=exc.attempts,
        )
        raise TelegramDeliveryError(
            "daily report photo delivery failed", attempts=exc.attempts
        ) from None
    record_photo_sent(
        connection,
        header.id,
        photo_receipt.message_id,
        photo_receipt.attempts,
    )
    connection.commit()
    return {
        "status": "sent",
        "snapshot_id": header.id,
        "text_message_id": text_message_id,
        "photo_message_id": photo_receipt.message_id,
    }
