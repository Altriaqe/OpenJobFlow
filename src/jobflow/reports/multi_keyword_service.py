"""多关键词日报服务：汇总趋势并管理 Telegram 图文投递幂等状态。"""

from collections.abc import Callable, Sequence
from datetime import date, timedelta

from jobflow.channels.telegram import (
    TelegramDeliveryError,
    TelegramDeliveryUncertain,
    TelegramReceipt,
    send_telegram_photo,
    send_telegram_text,
)
from jobflow.db.snapshots import (
    get_delivery,
    get_deliveries_for_update,
    get_snapshot,
    list_new_job_postings,
    list_snapshot_items,
    record_photo_failed,
    record_photo_sending,
    record_photo_sent,
    record_photo_uncertain,
    record_recovered_photo_sent,
    record_text_failed,
    record_text_sending,
    record_text_sent,
    record_text_uncertain,
)
from jobflow.models.snapshot import KeywordTrend, ReportDelivery, SnapshotHeader
from jobflow.reports.charts import (
    build_baseline_pending_png,
    build_keyword_city_heatmap_png,
)
from jobflow.reports.comparison import compare_daily, count_new_jobs_by_city
from jobflow.reports.daily_brief import build_multi_keyword_brief
from jobflow.reports.daily_service import load_weekly_comparison_if_sunday
from jobflow.reports.wechat_article import (
    KeywordNewJobs,
    WechatArticleData,
    build_article_data,
)

DAILY_KEYWORDS = ("AI Agent", "Python开发", "Java开发", "数据分析")


class MultiKeywordSnapshotMissing(Exception):
    def __init__(self, missing_keywords: tuple[str, ...]) -> None:
        self.missing_keywords = missing_keywords
        super().__init__(f"missing snapshots: {', '.join(missing_keywords)}")


class MultiKeywordScopeError(Exception):
    pass


class MultiKeywordDeliveryStateError(Exception):
    pass


def _validated_keywords(keywords: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(keyword.strip() for keyword in keywords)
    if not normalized or any(not keyword for keyword in normalized):
        raise ValueError("keywords must be non-empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("keywords must be unique")
    return normalized


def _load_headers(
    connection,
    *,
    snapshot_date: date,
    keywords: Sequence[str],
) -> tuple[tuple[SnapshotHeader, ...], tuple[str, ...]]:
    headers: list[SnapshotHeader] = []
    missing: list[str] = []
    for keyword in keywords:
        header = get_snapshot(
            connection,
            snapshot_date=snapshot_date,
            search_keyword=keyword,
        )
        if header is None:
            missing.append(keyword)
        else:
            headers.append(header)
    return tuple(headers), tuple(missing)


def _collection_scope(header: SnapshotHeader) -> tuple[tuple[str, ...], int, bool]:
    return tuple(sorted(header.cities)), header.pages_per_city, header.details_included


def _validate_shared_scope(headers: Sequence[SnapshotHeader]) -> None:
    scopes = {_collection_scope(header) for header in headers}
    if len(scopes) != 1:
        raise MultiKeywordScopeError("keyword snapshots use different collection scopes")


def _load_deliveries(connection, headers: Sequence[SnapshotHeader]) -> tuple[ReportDelivery, ...]:
    deliveries: list[ReportDelivery] = []
    for header in headers:
        delivery = get_delivery(connection, header.id)
        if delivery is None:
            raise MultiKeywordDeliveryStateError("daily delivery state not found")
        deliveries.append(delivery)
    return tuple(deliveries)


def _single_message_id(values: Sequence[int | None], *, field: str) -> int:
    unique = set(values)
    if len(unique) != 1 or None in unique:
        raise MultiKeywordDeliveryStateError(f"inconsistent {field}")
    return next(value for value in unique if value is not None)


def _optional_group_message_id(
    values: Sequence[int | None],
    *,
    field: str,
) -> int | None:
    unique = set(values)
    if len(unique) != 1:
        raise MultiKeywordDeliveryStateError(f"inconsistent {field}")
    return next(iter(unique))


def _group_delivery_state(
    deliveries: Sequence[ReportDelivery],
) -> tuple[str, int | None, int | None]:
    if not deliveries:
        raise MultiKeywordDeliveryStateError("daily delivery state not found")

    statuses = {delivery.status for delivery in deliveries}
    if len(statuses) != 1:
        raise MultiKeywordDeliveryStateError("keyword deliveries use different stages")
    status = next(iter(statuses))
    text_ids = [delivery.text_message_id for delivery in deliveries]
    photo_ids = [delivery.photo_message_id for delivery in deliveries]

    no_message_states = {
        "pending",
        "text_sending",
        "text_failed",
        "text_uncertain",
        "failed",
    }
    if status in no_message_states:
        if any(message_id is not None for message_id in (*text_ids, *photo_ids)):
            raise MultiKeywordDeliveryStateError("delivery stage contains unexpected message ids")
        return status, None, None
    if status in {"text_sent", "partial_failed"}:
        text_id = _single_message_id(text_ids, field="text message ids")
        if any(message_id is not None for message_id in photo_ids):
            raise MultiKeywordDeliveryStateError("text delivery contains photo ids")
        return status, text_id, None
    if status in {"photo_sending", "photo_failed", "photo_uncertain"}:
        text_id = _optional_group_message_id(text_ids, field="text message ids")
        if any(message_id is not None for message_id in photo_ids):
            raise MultiKeywordDeliveryStateError("photo delivery contains photo ids")
        return status, text_id, None
    if status == "completed":
        return (
            status,
            _single_message_id(text_ids, field="text message ids"),
            _single_message_id(photo_ids, field="photo message ids"),
        )
    if status == "completed_text_uncertain":
        if any(message_id is not None for message_id in text_ids):
            raise MultiKeywordDeliveryStateError("uncertain text contains message id")
        return (
            status,
            None,
            _single_message_id(photo_ids, field="photo message ids"),
        )
    raise MultiKeywordDeliveryStateError("unsupported delivery stage")


def _delivery_phase(
    deliveries: Sequence[ReportDelivery],
) -> tuple[str, int | None, int | None]:
    status, text_message_id, photo_message_id = _group_delivery_state(deliveries)
    if status in {"pending", "text_sent"}:
        return status, text_message_id, photo_message_id
    if status in {"completed", "completed_text_uncertain"}:
        return "completed", text_message_id, photo_message_id
    raise MultiKeywordDeliveryStateError(f"delivery stage requires manual action: {status}")


def get_multi_keyword_report_status(
    connection,
    *,
    snapshot_date: date,
    keywords: Sequence[str] = DAILY_KEYWORDS,
) -> dict[str, object]:
    """汇总各关键词快照和 Telegram 文字/图片状态，供 API 查询。"""
    normalized = _validated_keywords(keywords)
    headers, missing = _load_headers(
        connection,
        snapshot_date=snapshot_date,
        keywords=normalized,
    )
    if missing:
        present = [keyword for keyword in normalized if keyword not in set(missing)]
        return {
            "status": "missing_snapshots",
            "snapshot_date": snapshot_date.isoformat(),
            "present_keywords": present,
            "missing_keywords": list(missing),
        }

    _validate_shared_scope(headers)
    phase, text_message_id, photo_message_id = _group_delivery_state(
        _load_deliveries(connection, headers)
    )
    manual_states = {
        "text_sending",
        "text_failed",
        "text_uncertain",
        "photo_sending",
        "photo_failed",
        "photo_uncertain",
        "failed",
        "partial_failed",
    }
    return {
        "status": phase,
        "snapshot_date": snapshot_date.isoformat(),
        "keywords": list(normalized),
        "text_sent": text_message_id is not None,
        "photo_sent": photo_message_id is not None,
        "manual_action_required": phase in manual_states,
    }


def _build_trends(
    connection,
    *,
    snapshot_date: date,
    headers: Sequence[SnapshotHeader],
) -> tuple[KeywordTrend, ...]:
    trends: list[KeywordTrend] = []
    for header in headers:
        current_items = list_snapshot_items(connection, header.id)
        previous_header = get_snapshot(
            connection,
            snapshot_date=snapshot_date - timedelta(days=1),
            search_keyword=header.search_keyword,
        )
        if previous_header is not None and _collection_scope(previous_header) != _collection_scope(
            header
        ):
            previous_header = None
        previous_items = (
            None if previous_header is None else list_snapshot_items(connection, previous_header.id)
        )
        daily = compare_daily(current_items, previous_items, cities=header.cities)
        new_by_city = count_new_jobs_by_city(
            current_items,
            previous_items,
            cities=header.cities,
        )
        weekly = load_weekly_comparison_if_sunday(
            connection,
            report_date=snapshot_date,
            keyword=header.search_keyword,
            current_header=header,
        )
        trends.append(KeywordTrend(header.search_keyword, daily, new_by_city, weekly))
    return tuple(trends)


def _load_new_job_groups(
    connection,
    *,
    snapshot_date: date,
    headers: Sequence[SnapshotHeader],
) -> tuple[KeywordNewJobs, ...]:
    """按关键词顺序加载前日差集，并保留“无基线”和“零新增”的区别。"""
    groups: list[KeywordNewJobs] = []
    for header in headers:
        previous = get_snapshot(
            connection,
            snapshot_date=snapshot_date - timedelta(days=1),
            search_keyword=header.search_keyword,
        )
        if previous is None or _collection_scope(previous) != _collection_scope(header):
            groups.append(KeywordNewJobs(header.search_keyword, None))
            continue
        postings = list_new_job_postings(
            connection,
            current_snapshot_id=header.id,
            previous_snapshot_id=previous.id,
            keyword=header.search_keyword,
        )
        groups.append(KeywordNewJobs(header.search_keyword, postings))
    return tuple(groups)


def _record_group_result(
    connection,
    *,
    snapshot_ids: Sequence[int],
    recorder: Callable[[object, int, str, int], None],
    error_type: str,
    attempts: int,
) -> None:
    for snapshot_id in snapshot_ids:
        recorder(connection, snapshot_id, error_type, attempts)
    connection.commit()


def _lock_deliveries(connection, snapshot_ids: list[int]) -> tuple[ReportDelivery, ...]:
    try:
        return get_deliveries_for_update(connection, snapshot_ids)
    except ValueError as exc:
        connection.rollback()
        raise MultiKeywordDeliveryStateError("daily delivery group is incomplete") from exc


def _claim_text(connection, snapshot_ids: list[int]) -> None:
    """在事务内认领文字发送，避免同一天同渠道重复发送。"""
    deliveries = _lock_deliveries(connection, snapshot_ids)
    try:
        phase, _text_message_id, _photo_message_id = _delivery_phase(deliveries)
    except MultiKeywordDeliveryStateError:
        connection.rollback()
        raise
    if phase != "pending":
        connection.rollback()
        raise MultiKeywordDeliveryStateError("text delivery cannot be claimed")
    for snapshot_id in snapshot_ids:
        record_text_sending(connection, snapshot_id)
    connection.commit()


def _claim_photo(connection, snapshot_ids: list[int]) -> int:
    """在文字成功后认领图片发送，返回需要发送的快照数量。"""
    deliveries = _lock_deliveries(connection, snapshot_ids)
    try:
        phase, text_message_id, _photo_message_id = _delivery_phase(deliveries)
    except MultiKeywordDeliveryStateError:
        connection.rollback()
        raise
    if phase == "completed":
        connection.rollback()
        raise MultiKeywordDeliveryStateError("photo delivery is already complete")
    if phase != "text_sent" or text_message_id is None:
        connection.rollback()
        raise MultiKeywordDeliveryStateError("photo delivery cannot be claimed")
    for snapshot_id in snapshot_ids:
        record_photo_sending(connection, snapshot_id)
    connection.commit()
    return text_message_id


def _build_report_parts(
    connection,
    *,
    snapshot_date: date,
    headers: Sequence[SnapshotHeader],
) -> tuple[str, bytes]:
    trends = _build_trends(
        connection,
        snapshot_date=snapshot_date,
        headers=headers,
    )
    text = build_multi_keyword_brief(
        report_date=snapshot_date,
        trends=trends,
        city_count=headers[0].city_count,
        pages_per_city=headers[0].pages_per_city,
    )
    image = (
        build_keyword_city_heatmap_png(trends, cities=headers[0].cities)
        if all(trend.new_by_city is not None for trend in trends)
        else build_baseline_pending_png()
    )
    return text, image


def build_multi_keyword_wechat_parts(
    connection,
    *,
    snapshot_date: date,
    keywords: Sequence[str] = DAILY_KEYWORDS,
) -> tuple[WechatArticleData, bytes]:
    """复用 Telegram 的多关键词趋势口径，生成微信文章数据和同一张趋势图。"""
    normalized = _validated_keywords(keywords)
    headers, missing = _load_headers(connection, snapshot_date=snapshot_date, keywords=normalized)
    if missing:
        raise MultiKeywordSnapshotMissing(missing)
    _validate_shared_scope(headers)
    trends = _build_trends(connection, snapshot_date=snapshot_date, headers=headers)
    new_job_groups = _load_new_job_groups(
        connection,
        snapshot_date=snapshot_date,
        headers=headers,
    )
    image = (
        build_keyword_city_heatmap_png(trends, cities=headers[0].cities)
        if all(trend.new_by_city is not None for trend in trends)
        else build_baseline_pending_png()
    )
    article_data = build_article_data(
        report_date=snapshot_date,
        trends=trends,
        city_count=headers[0].city_count,
        cities=headers[0].cities,
        pages_per_city=headers[0].pages_per_city,
        new_job_groups=new_job_groups,
    )
    return article_data, image


def send_multi_keyword_report(
    connection,
    *,
    snapshot_date: date,
    keywords: Sequence[str] = DAILY_KEYWORDS,
    text_sender: Callable[[str], TelegramReceipt] | None = None,
    photo_sender: Callable[[bytes], TelegramReceipt] | None = None,
) -> dict[str, object]:
    """构建多关键词日报并完成 Telegram 图文发送，状态写入与发送解耦。"""

    normalized = _validated_keywords(keywords)
    headers, missing = _load_headers(
        connection,
        snapshot_date=snapshot_date,
        keywords=normalized,
    )
    if missing:
        raise MultiKeywordSnapshotMissing(missing)
    _validate_shared_scope(headers)

    snapshot_ids = [header.id for header in headers]
    phase, text_message_id, _photo_message_id = _delivery_phase(
        _load_deliveries(connection, headers)
    )
    if phase == "completed":
        return {"status": "already_sent", "snapshot_ids": snapshot_ids}

    text, image = _build_report_parts(
        connection,
        snapshot_date=snapshot_date,
        headers=headers,
    )
    selected_text_sender = text_sender or (lambda value: send_telegram_text(value, max_attempts=1))
    selected_photo_sender = photo_sender or (
        lambda value: send_telegram_photo(value, max_attempts=1)
    )

    if phase == "pending":
        _claim_text(connection, snapshot_ids)
        try:
            text_receipt = selected_text_sender(text)
        except TelegramDeliveryUncertain as exc:
            _record_group_result(
                connection,
                snapshot_ids=snapshot_ids,
                recorder=record_text_uncertain,
                error_type="telegram_delivery_uncertain",
                attempts=exc.attempts,
            )
            raise TelegramDeliveryUncertain(
                "multi-keyword report text delivery is uncertain",
                attempts=exc.attempts,
            ) from None
        except TelegramDeliveryError as exc:
            _record_group_result(
                connection,
                snapshot_ids=snapshot_ids,
                recorder=record_text_failed,
                error_type="telegram_delivery",
                attempts=exc.attempts,
            )
            raise TelegramDeliveryError(
                "multi-keyword report text delivery failed",
                attempts=exc.attempts,
            ) from None
        for snapshot_id in snapshot_ids:
            record_text_sent(
                connection,
                snapshot_id,
                text_receipt.message_id,
                text_receipt.attempts,
            )
        connection.commit()
        text_message_id = text_receipt.message_id

    text_message_id = _claim_photo(connection, snapshot_ids)
    try:
        photo_receipt = selected_photo_sender(image)
    except TelegramDeliveryUncertain as exc:
        _record_group_result(
            connection,
            snapshot_ids=snapshot_ids,
            recorder=record_photo_uncertain,
            error_type="telegram_delivery_uncertain",
            attempts=exc.attempts,
        )
        raise TelegramDeliveryUncertain(
            "multi-keyword report photo delivery is uncertain",
            attempts=exc.attempts,
        ) from None
    except TelegramDeliveryError as exc:
        _record_group_result(
            connection,
            snapshot_ids=snapshot_ids,
            recorder=record_photo_failed,
            error_type="telegram_delivery",
            attempts=exc.attempts,
        )
        raise TelegramDeliveryError(
            "multi-keyword report photo delivery failed",
            attempts=exc.attempts,
        ) from None
    for snapshot_id in snapshot_ids:
        record_photo_sent(
            connection,
            snapshot_id,
            photo_receipt.message_id,
            photo_receipt.attempts,
        )
    connection.commit()
    return {
        "status": "sent",
        "snapshot_ids": snapshot_ids,
        "text_message_id": text_message_id,
        "photo_message_id": photo_receipt.message_id,
    }


def _recovery_text_receipt_known(deliveries: Sequence[ReportDelivery]) -> bool:
    status, text_message_id, _photo_message_id = _group_delivery_state(deliveries)
    if status == "text_uncertain":
        return False
    if status == "failed":
        if not all(
            (delivery.last_error_type or "").startswith("telegram_") for delivery in deliveries
        ):
            raise MultiKeywordDeliveryStateError("legacy failure has no Telegram evidence")
        return False
    if status == "partial_failed" and text_message_id is not None:
        return True
    raise MultiKeywordDeliveryStateError("delivery stage cannot recover photo")


def recover_multi_keyword_report_photo(
    connection,
    *,
    snapshot_date: date,
    confirm_text_visible: bool,
    keywords: Sequence[str] = DAILY_KEYWORDS,
    photo_sender: Callable[[bytes], TelegramReceipt] | None = None,
) -> dict[str, object]:
    """仅在显式确认文字未收到时补发图片，避免不确定结果造成重复消息。"""

    if not confirm_text_visible:
        raise MultiKeywordDeliveryStateError("visible text confirmation required")

    normalized = _validated_keywords(keywords)
    headers, missing = _load_headers(
        connection,
        snapshot_date=snapshot_date,
        keywords=normalized,
    )
    if missing:
        raise MultiKeywordSnapshotMissing(missing)
    _validate_shared_scope(headers)
    snapshot_ids = [header.id for header in headers]

    _text, image = _build_report_parts(
        connection,
        snapshot_date=snapshot_date,
        headers=headers,
    )
    deliveries = _lock_deliveries(connection, snapshot_ids)
    try:
        text_receipt_known = _recovery_text_receipt_known(deliveries)
    except MultiKeywordDeliveryStateError:
        connection.rollback()
        raise
    for snapshot_id in snapshot_ids:
        record_photo_sending(connection, snapshot_id)
    connection.commit()

    selected_photo_sender = photo_sender or (
        lambda value: send_telegram_photo(value, max_attempts=1)
    )
    try:
        photo_receipt = selected_photo_sender(image)
    except TelegramDeliveryUncertain as exc:
        _record_group_result(
            connection,
            snapshot_ids=snapshot_ids,
            recorder=record_photo_uncertain,
            error_type="telegram_delivery_uncertain",
            attempts=exc.attempts,
        )
        raise TelegramDeliveryUncertain(
            "multi-keyword report photo delivery is uncertain",
            attempts=exc.attempts,
        ) from None
    except TelegramDeliveryError as exc:
        _record_group_result(
            connection,
            snapshot_ids=snapshot_ids,
            recorder=record_photo_failed,
            error_type="telegram_delivery",
            attempts=exc.attempts,
        )
        raise TelegramDeliveryError(
            "multi-keyword report photo delivery failed",
            attempts=exc.attempts,
        ) from None

    for snapshot_id in snapshot_ids:
        record_recovered_photo_sent(
            connection,
            snapshot_id,
            message_id=photo_receipt.message_id,
            attempts=photo_receipt.attempts,
            text_receipt_known=text_receipt_known,
        )
    connection.commit()
    return {
        "status": "sent",
        "snapshot_ids": snapshot_ids,
        "photo_message_id": photo_receipt.message_id,
        "text_receipt_known": text_receipt_known,
    }
