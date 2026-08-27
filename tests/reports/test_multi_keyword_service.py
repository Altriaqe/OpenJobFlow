from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from jobflow.channels.telegram import (
    TelegramDeliveryError,
    TelegramDeliveryUncertain,
    TelegramReceipt,
)
from jobflow.models.snapshot import (
    DailyComparison,
    MetricChange,
    NamedCount,
    NewJobPosting,
    ReportDelivery,
    SnapshotHeader,
)
from jobflow.reports import multi_keyword_service

REPORT_DATE = date(2026, 8, 20)
KEYWORDS = ("AI Agent", "Python开发", "Java开发", "数据分析")
CITIES = ("上海", "北京", "杭州", "深圳")


def header(
    keyword: str,
    snapshot_id: int,
    *,
    snapshot_date: date = REPORT_DATE,
    pages: int = 3,
) -> SnapshotHeader:
    return SnapshotHeader(
        id=snapshot_id,
        snapshot_date=snapshot_date,
        search_keyword=keyword,
        batch_id=100 + snapshot_id,
        city_count=4,
        cities=CITIES,
        pages_per_city=pages,
        details_included=False,
    )


def delivery(
    snapshot_id: int,
    status: str = "pending",
    *,
    text_message_id: int | None = None,
    photo_message_id: int | None = None,
    last_error_type: str | None = None,
) -> ReportDelivery:
    return ReportDelivery(
        snapshot_id=snapshot_id,
        status=status,
        text_message_id=text_message_id,
        photo_message_id=photo_message_id,
        text_attempts=0,
        photo_attempts=0,
        last_error_type=last_error_type,
    )


def posting(keyword: str, external_id: str) -> NewJobPosting:
    return NewJobPosting(
        source="boss_zhipin",
        external_id=external_id,
        keyword=keyword,
        title=f"{keyword} 工程师",
        company="示例公司",
        city="上海",
        salary_text="20-30K",
        salary_min=20,
        salary_max=30,
        salary_unit="K_PER_MONTH",
        salary_months=None,
        skills=("Python",),
        detail_url=f"https://example.test/jobs/{external_id}",
    )


def daily_comparison(*, has_baseline: bool) -> DailyComparison:
    previous = 10 if has_baseline else None
    return DailyComparison(
        has_baseline=has_baseline,
        total=MetricChange(12, previous, 2 if has_baseline else None, Decimal("20.0")),
        city_metrics=(),
        new_count=4 if has_baseline else None,
        continued_count=8 if has_baseline else None,
        missing_count=2 if has_baseline else None,
        skills=(),
        salary_midpoint_median=MetricChange(None, None, None, None),
    )


def arrange(
    monkeypatch,
    *,
    present: tuple[str, ...] = KEYWORDS,
    with_baseline: bool = True,
    delivery_status: str = "pending",
    text_message_id: int | None = None,
    photo_message_id: int | None = None,
    pages_by_keyword: dict[str, int] | None = None,
    last_error_type: str | None = None,
    locked_statuses: tuple[str, ...] | None = None,
) -> Mock:
    pages_by_keyword = pages_by_keyword or {}
    current = {
        keyword: header(keyword, 11 + index, pages=pages_by_keyword.get(keyword, 3))
        for index, keyword in enumerate(KEYWORDS)
        if keyword in present
    }
    previous = {
        keyword: header(
            keyword,
            21 + index,
            snapshot_date=REPORT_DATE - timedelta(days=1),
            pages=pages_by_keyword.get(keyword, 3),
        )
        for index, keyword in enumerate(KEYWORDS)
        if keyword in present and with_baseline
    }

    def get_snapshot(_connection, *, snapshot_date, search_keyword):
        if snapshot_date == REPORT_DATE:
            return current.get(search_keyword)
        if snapshot_date == REPORT_DATE - timedelta(days=1):
            return previous.get(search_keyword)
        return None

    monkeypatch.setattr(multi_keyword_service, "get_snapshot", get_snapshot)
    monkeypatch.setattr(
        multi_keyword_service,
        "get_delivery",
        lambda _connection, snapshot_id: delivery(
            snapshot_id,
            delivery_status,
            text_message_id=text_message_id,
            photo_message_id=photo_message_id,
            last_error_type=last_error_type,
        ),
    )
    if locked_statuses is None:
        locked_statuses = (
            ("pending", "text_sent") if delivery_status == "pending" else (delivery_status,)
        )
    locked_queue = list(locked_statuses)

    def get_deliveries_for_update(_connection, snapshot_ids):
        if not locked_queue:
            raise AssertionError("unexpected delivery lock")
        status = locked_queue.pop(0)
        locked_text_id = text_message_id
        if status == "text_sent" and locked_text_id is None:
            locked_text_id = 101
        return tuple(
            delivery(
                snapshot_id,
                status,
                text_message_id=locked_text_id,
                photo_message_id=photo_message_id,
                last_error_type=last_error_type,
            )
            for snapshot_id in snapshot_ids
        )

    monkeypatch.setattr(
        multi_keyword_service,
        "get_deliveries_for_update",
        Mock(side_effect=get_deliveries_for_update),
    )
    monkeypatch.setattr(multi_keyword_service, "list_snapshot_items", Mock(return_value=()))
    monkeypatch.setattr(
        multi_keyword_service,
        "list_new_job_postings",
        Mock(return_value=()),
    )
    monkeypatch.setattr(
        multi_keyword_service,
        "compare_daily",
        Mock(return_value=daily_comparison(has_baseline=with_baseline)),
    )
    monkeypatch.setattr(
        multi_keyword_service,
        "count_new_jobs_by_city",
        Mock(
            return_value=(tuple(NamedCount(city, 1) for city in CITIES) if with_baseline else None)
        ),
    )
    monkeypatch.setattr(
        multi_keyword_service,
        "load_weekly_comparison_if_sunday",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        multi_keyword_service, "build_multi_keyword_brief", Mock(return_value="合并简报")
    )
    monkeypatch.setattr(
        multi_keyword_service,
        "build_keyword_city_heatmap_png",
        Mock(return_value=b"heatmap"),
    )
    monkeypatch.setattr(
        multi_keyword_service, "build_baseline_pending_png", Mock(return_value=b"baseline")
    )
    for name in (
        "record_text_sending",
        "record_text_sent",
        "record_text_failed",
        "record_text_uncertain",
        "record_photo_sending",
        "record_photo_sent",
        "record_photo_failed",
        "record_photo_uncertain",
        "record_recovered_photo_sent",
    ):
        monkeypatch.setattr(multi_keyword_service, name, Mock())
    return Mock()


def test_wechat_parts_include_all_new_jobs_in_keyword_order(monkeypatch) -> None:
    connection = arrange(monkeypatch)

    def new_jobs(_connection, *, current_snapshot_id, previous_snapshot_id, keyword):
        assert current_snapshot_id < previous_snapshot_id
        return (posting(keyword, f"job-{current_snapshot_id}"),)

    multi_keyword_service.list_new_job_postings.side_effect = new_jobs

    data, _image = multi_keyword_service.build_multi_keyword_wechat_parts(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    assert tuple(group.keyword for group in data.new_job_groups) == KEYWORDS
    assert tuple(group.postings[0].keyword for group in data.new_job_groups) == KEYWORDS
    assert multi_keyword_service.list_new_job_postings.call_count == 4


def test_wechat_parts_distinguish_missing_baseline_from_empty_diff(monkeypatch) -> None:
    connection = arrange(monkeypatch, with_baseline=False)

    data, _image = multi_keyword_service.build_multi_keyword_wechat_parts(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    assert all(group.postings is None for group in data.new_job_groups)
    multi_keyword_service.list_new_job_postings.assert_not_called()


def test_wechat_parts_keep_empty_tuple_when_baseline_has_no_new_jobs(monkeypatch) -> None:
    connection = arrange(monkeypatch)

    data, _image = multi_keyword_service.build_multi_keyword_wechat_parts(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    assert all(group.postings == () for group in data.new_job_groups)


def test_status_lists_only_missing_keywords(monkeypatch) -> None:
    connection = arrange(monkeypatch, present=("AI Agent", "Java开发"))

    result = multi_keyword_service.get_multi_keyword_report_status(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    assert result == {
        "status": "missing_snapshots",
        "snapshot_date": "2026-08-20",
        "present_keywords": ["AI Agent", "Java开发"],
        "missing_keywords": ["Python开发", "数据分析"],
    }


def test_send_refuses_partial_snapshot_set(monkeypatch) -> None:
    connection = arrange(monkeypatch, present=KEYWORDS[:-1])

    with pytest.raises(multi_keyword_service.MultiKeywordSnapshotMissing, match="数据分析"):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
        )


def test_send_records_same_message_ids_for_all_snapshots(monkeypatch) -> None:
    connection = arrange(monkeypatch)

    result = multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=Mock(return_value=TelegramReceipt(101, 1)),
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert result == {
        "status": "sent",
        "snapshot_ids": [11, 12, 13, 14],
        "text_message_id": 101,
        "photo_message_id": 202,
    }
    assert multi_keyword_service.record_text_sent.call_count == 4
    assert multi_keyword_service.record_photo_sent.call_count == 4
    assert connection.commit.call_count == 4


def test_text_sent_resumes_photo_without_duplicate_text(monkeypatch) -> None:
    connection = arrange(
        monkeypatch,
        delivery_status="text_sent",
        text_message_id=101,
    )
    text_sender = Mock()

    result = multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=text_sender,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    text_sender.assert_not_called()
    assert result["status"] == "sent"
    assert result["text_message_id"] == 101


def test_partial_failed_requires_explicit_recovery(monkeypatch) -> None:
    connection = arrange(
        monkeypatch,
        delivery_status="partial_failed",
        text_message_id=101,
    )
    text_sender = Mock()
    photo_sender = Mock()

    with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    text_sender.assert_not_called()
    photo_sender.assert_not_called()


def test_completed_group_returns_already_sent_without_rendering(monkeypatch) -> None:
    connection = arrange(
        monkeypatch,
        delivery_status="completed",
        text_message_id=101,
        photo_message_id=202,
    )

    result = multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    assert result == {
        "status": "already_sent",
        "snapshot_ids": [11, 12, 13, 14],
    }
    multi_keyword_service.build_multi_keyword_brief.assert_not_called()


def test_first_day_uses_baseline_image_instead_of_heatmap(monkeypatch) -> None:
    connection = arrange(monkeypatch, with_baseline=False)
    photo_sender = Mock(return_value=TelegramReceipt(202, 1))

    multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=Mock(return_value=TelegramReceipt(101, 1)),
        photo_sender=photo_sender,
    )

    photo_sender.assert_called_once_with(b"baseline")
    multi_keyword_service.build_keyword_city_heatmap_png.assert_not_called()


def test_mismatched_keyword_scope_is_rejected(monkeypatch) -> None:
    connection = arrange(monkeypatch, pages_by_keyword={"数据分析": 2})

    with pytest.raises(multi_keyword_service.MultiKeywordScopeError):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
        )


def test_text_failure_is_recorded_for_all_keyword_snapshots(monkeypatch) -> None:
    connection = arrange(monkeypatch)

    with pytest.raises(TelegramDeliveryError) as exc_info:
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=Mock(side_effect=TelegramDeliveryError("secret", attempts=1)),
            photo_sender=Mock(),
        )

    assert exc_info.value.attempts == 1
    assert "secret" not in str(exc_info.value)
    assert multi_keyword_service.record_text_failed.call_count == 4
    assert connection.commit.call_count == 2


def test_photo_failure_is_recorded_for_all_keyword_snapshots(monkeypatch) -> None:
    connection = arrange(monkeypatch)

    with pytest.raises(TelegramDeliveryError):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=Mock(return_value=TelegramReceipt(101, 1)),
            photo_sender=Mock(side_effect=TelegramDeliveryError("secret", attempts=1)),
        )

    assert multi_keyword_service.record_text_sent.call_count == 4
    assert multi_keyword_service.record_photo_failed.call_count == 4
    assert connection.commit.call_count == 4


def test_text_is_preclaimed_and_committed_before_sender(monkeypatch) -> None:
    connection = arrange(monkeypatch)
    observed_commit_counts: list[int] = []

    def text_sender(_text: str) -> TelegramReceipt:
        observed_commit_counts.append(connection.commit.call_count)
        return TelegramReceipt(101, 1)

    multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=text_sender,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert observed_commit_counts == [1]
    assert multi_keyword_service.record_text_sending.call_count == 4
    assert multi_keyword_service.record_photo_sending.call_count == 4


def test_default_multi_keyword_senders_force_one_attempt(monkeypatch) -> None:
    connection = arrange(monkeypatch)
    text_sender = Mock(return_value=TelegramReceipt(101, 1))
    photo_sender = Mock(return_value=TelegramReceipt(202, 1))
    monkeypatch.setattr(multi_keyword_service, "send_telegram_text", text_sender)
    monkeypatch.setattr(multi_keyword_service, "send_telegram_photo", photo_sender)

    multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    text_sender.assert_called_once_with("合并简报", max_attempts=1)
    photo_sender.assert_called_once_with(b"heatmap", max_attempts=1)


def test_second_request_cannot_send_after_first_preclaim(monkeypatch) -> None:
    first_connection = arrange(
        monkeypatch,
        locked_statuses=("pending", "text_sending", "text_sent"),
    )
    second_connection = Mock()
    sender_calls = 0

    def shared_sender(_text: str) -> TelegramReceipt:
        nonlocal sender_calls
        sender_calls += 1
        with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
            multi_keyword_service.send_multi_keyword_report(
                second_connection,
                snapshot_date=REPORT_DATE,
                keywords=KEYWORDS,
                text_sender=shared_sender,
                photo_sender=Mock(),
            )
        return TelegramReceipt(101, 1)

    result = multi_keyword_service.send_multi_keyword_report(
        first_connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=shared_sender,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert result["status"] == "sent"
    assert sender_calls == 1
    second_connection.rollback.assert_called_once_with()


def test_text_timeout_becomes_uncertain_without_photo(monkeypatch) -> None:
    connection = arrange(monkeypatch, locked_statuses=("pending",))
    text_sender = Mock(side_effect=TelegramDeliveryUncertain("hidden", attempts=1))
    photo_sender = Mock()

    with pytest.raises(TelegramDeliveryUncertain) as exc_info:
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    assert exc_info.value.attempts == 1
    assert "hidden" not in str(exc_info.value)
    text_sender.assert_called_once_with("合并简报")
    photo_sender.assert_not_called()
    assert multi_keyword_service.record_text_uncertain.call_count == 4
    assert connection.commit.call_count == 2


def test_photo_timeout_preserves_text_and_becomes_uncertain(monkeypatch) -> None:
    connection = arrange(monkeypatch)
    photo_sender = Mock(side_effect=TelegramDeliveryUncertain("hidden", attempts=1))

    with pytest.raises(TelegramDeliveryUncertain):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=Mock(return_value=TelegramReceipt(101, 1)),
            photo_sender=photo_sender,
        )

    photo_sender.assert_called_once()
    assert multi_keyword_service.record_text_sent.call_count == 4
    assert multi_keyword_service.record_photo_uncertain.call_count == 4
    assert connection.commit.call_count == 4


@pytest.mark.parametrize(
    "blocked_status",
    [
        "text_sending",
        "text_failed",
        "text_uncertain",
        "photo_sending",
        "photo_failed",
        "photo_uncertain",
        "failed",
    ],
)
def test_ordinary_send_never_retries_blocked_stage(monkeypatch, blocked_status) -> None:
    connection = arrange(monkeypatch, delivery_status=blocked_status)
    text_sender = Mock()
    photo_sender = Mock()

    with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    text_sender.assert_not_called()
    photo_sender.assert_not_called()


def test_uncertain_status_requires_manual_action(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")

    result = multi_keyword_service.get_multi_keyword_report_status(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
    )

    assert result["status"] == "text_uncertain"
    assert result["text_sent"] is False
    assert result["photo_sent"] is False
    assert result["manual_action_required"] is True


def test_recovery_requires_explicit_visible_confirmation(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")
    photo_sender = Mock()

    with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
        multi_keyword_service.recover_multi_keyword_report_photo(
            connection,
            snapshot_date=REPORT_DATE,
            confirm_text_visible=False,
            keywords=KEYWORDS,
            photo_sender=photo_sender,
        )

    photo_sender.assert_not_called()


def test_recovery_sends_only_photo_once(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")
    photo_sender = Mock(return_value=TelegramReceipt(202, 1))

    result = multi_keyword_service.recover_multi_keyword_report_photo(
        connection,
        snapshot_date=REPORT_DATE,
        confirm_text_visible=True,
        keywords=KEYWORDS,
        photo_sender=photo_sender,
    )

    photo_sender.assert_called_once_with(b"heatmap")
    assert result == {
        "status": "sent",
        "snapshot_ids": [11, 12, 13, 14],
        "photo_message_id": 202,
        "text_receipt_known": False,
    }
    assert multi_keyword_service.record_text_sending.call_count == 0
    assert multi_keyword_service.record_photo_sending.call_count == 4
    assert multi_keyword_service.record_recovered_photo_sent.call_count == 4
    for call in multi_keyword_service.record_recovered_photo_sent.call_args_list:
        assert call.kwargs["text_receipt_known"] is False


def test_legacy_failed_recovery_requires_telegram_evidence(monkeypatch) -> None:
    connection = arrange(
        monkeypatch,
        delivery_status="failed",
        last_error_type="database_error",
    )
    photo_sender = Mock()

    with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
        multi_keyword_service.recover_multi_keyword_report_photo(
            connection,
            snapshot_date=REPORT_DATE,
            confirm_text_visible=True,
            keywords=KEYWORDS,
            photo_sender=photo_sender,
        )

    photo_sender.assert_not_called()
    connection.rollback.assert_called_once_with()


def test_partial_failed_recovery_preserves_known_text_receipt(monkeypatch) -> None:
    connection = arrange(
        monkeypatch,
        delivery_status="partial_failed",
        text_message_id=101,
    )

    result = multi_keyword_service.recover_multi_keyword_report_photo(
        connection,
        snapshot_date=REPORT_DATE,
        confirm_text_visible=True,
        keywords=KEYWORDS,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert result["text_receipt_known"] is True
    for call in multi_keyword_service.record_recovered_photo_sent.call_args_list:
        assert call.kwargs["text_receipt_known"] is True


def test_recovery_photo_timeout_stops_without_retry(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")
    photo_sender = Mock(side_effect=TelegramDeliveryUncertain("hidden", attempts=1))

    with pytest.raises(TelegramDeliveryUncertain):
        multi_keyword_service.recover_multi_keyword_report_photo(
            connection,
            snapshot_date=REPORT_DATE,
            confirm_text_visible=True,
            keywords=KEYWORDS,
            photo_sender=photo_sender,
        )

    photo_sender.assert_called_once()
    assert multi_keyword_service.record_photo_uncertain.call_count == 4
    assert connection.commit.call_count == 2
